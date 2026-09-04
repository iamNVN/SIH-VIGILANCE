"""
activity_simulator.py -- keeps Command Center's Live Investigation Feed
populated between real user actions.

REAL NEW CASES, ON A THROTTLED REAL SCHEDULE
-------------------------------------------------------------------
"New complaint received" actually reveals a real held-back complaint (see
core/replay_state.py -- the same per-city holdback Simulate Complaint
manually advances) via replay_state.advance(), which is a genuine DB write:
it flips that complaint's `revealed` flag, so /stats' total_complaints,
open_complaints and everything downstream actually move, exactly as if an
investigator had clicked Simulate Complaint themselves. This used to just
re-narrate an ALREADY-revealed complaint (no DB write, so Total
Complaints never budged even as the feed kept saying "new complaint
received") -- verified live, and fixed here.

Because each injection is a real, finite resource (only
scripts/seed_db.py's HOLDBACK_PER_CITY complaints are held back per city
at seed time), this is rate-limited to roughly once every 3-4 minutes
(_NEW_CASE_MIN/MAX_INTERVAL_SECONDS), not the few-second cadence the other
event types use, and gated by core/settings_state.py's "Inject Live Cases"
toggle (Settings page) -- OFF means no automatic injection at all; a real
investigator's own Simulate Complaint click is unaffected either way.

Prediction/ring events still sample real cached data (a real complaint's
real cached prediction, a real detected ring's real stats) on the faster
cadence -- those were never the part that needed slowing down or gating.

EACH CASE TELLS ONE COHERENT STORY, NOT THREE UNRELATED SAMPLES
-------------------------------------------------------------------
`_stories` tracks complaints actually moving through
received -> predicted -> decided, so the SAME case id (and, once
predicted, the SAME predicted location) shows up consistently across that
case's own events, the way a real investigation would read -- not an
unrelated random complaint sampled fresh for each event type.

The one type with no real-data anchor is the simulated decision
(approve/reject) -- it does NOT write to the complaint's actual `status`
(that only happens through complaints.py's real, investigator-triggered
/decision endpoint) -- a decision needs a human's judgment, not an
automatic timer. It's still the SAME case id and the SAME predicted
location the earlier "prediction generated" event for it showed.
"""

import random
import threading
import time

from core import event_log, settings_state
from core.case_code import case_code

_MIN_INTERVAL_SECONDS = 4
_MAX_INTERVAL_SECONDS = 9
_MAX_ACTIVE_STORIES = 6

_NEW_CASE_MIN_INTERVAL_SECONDS = 180
_NEW_CASE_MAX_INTERVAL_SECONDS = 240
_RING_MIN_INTERVAL_SECONDS = 45
_RING_MAX_INTERVAL_SECONDS = 90

# complaint_id -> {"stage": "received"|"predicted", "city": str|None,
# "location": str|None, "confidence": float|None} -- in-memory, one
# process's worth of "which simulated cases are mid-story right now".
_stories: dict[int, dict] = {}
_lock = threading.Lock()
# Own throttle for real injections specifically, separate from the general
# _emit_one() tick -- re-rolled after each real injection so the next one
# is again 3-4 real minutes out, not a fixed schedule.
_next_new_case_at = [0.0]
# Ditto for ring_found: it has no natural pacing of its own (unlike
# predict/decide, which are limited by how many stories are actually in
# flight) -- without this it was the ONLY thing with something to say on
# almost every idle tick between real case arrivals, so the feed read as
# ring-detection spam with the actual case updates buried a dozen entries
# deep. Verified live: 42 of 50 stored events were ring_detected.
_next_ring_at = [0.0]


def _start_story():
    if not settings_state.get_inject_live_cases():
        return
    now = time.time()
    with _lock:
        if now < _next_new_case_at[0]:
            return
        if len(_stories) >= _MAX_ACTIVE_STORIES:
            return

    from core import replay_state
    from core.db import SessionLocal

    from api.feed import add_revealed_complaint_to_feed

    db = SessionLocal()
    try:
        # No city filter -- reveals whichever held-back complaint is
        # globally next by filed_at, same as the live-replay WebSocket's
        # own automatic advance. A real investigator's own city-scoped
        # Simulate Complaint click is a completely separate call and
        # unaffected by this running or not.
        complaint = replay_state.advance(db)
        if complaint is None:
            return  # every held-back complaint has already been revealed
        add_revealed_complaint_to_feed(complaint)
        city = complaint.victim.city if complaint.victim else None
        with _lock:
            _stories[complaint.id] = {"stage": "received", "city": city, "bank": complaint.bank_name}
            _next_new_case_at[0] = now + random.uniform(_NEW_CASE_MIN_INTERVAL_SECONDS, _NEW_CASE_MAX_INTERVAL_SECONDS)
        event_log.log_event(
            "complaint_received",
            f"Case #{case_code(complaint.id)} — New complaint received",
            f"₹{complaint.amount_lost:,.0f} · {city or 'Unknown city'}",
            city,
        )
    finally:
        db.close()


def _advance_to_prediction():
    from api.feed import cached_feed_if_warm

    with _lock:
        received = [cid for cid, s in _stories.items() if s["stage"] == "received"]
    if not received:
        return
    cid = random.choice(received)
    items = cached_feed_if_warm() or []
    match = next((it for it in items if it["complaint_id"] == cid), None)
    if match is None:
        # Genuinely shouldn't happen (this cid was drawn from this same
        # cache), but if the cache reshuffled underneath us (a real
        # decision on this exact complaint mid-story, say), self-heal by
        # abandoning the story instead of leaving a permanently stuck slot.
        with _lock:
            _stories.pop(cid, None)
        return
    tp = match["top_prediction"]
    with _lock:
        story = _stories.get(cid)
        if story is None or story["stage"] != "received":
            return
        story.update(stage="predicted", location=tp["name"], confidence=tp["confidence"])
        city = story["city"]
    event_log.log_event(
        "prediction_generated",
        f"Case #{case_code(cid)} — Cash-out prediction generated",
        f"{tp['name']} · {round(tp['confidence'] * 100, 1)}%",
        city,
    )


def _advance_to_decision():
    with _lock:
        predicted = [cid for cid, s in _stories.items() if s["stage"] == "predicted"]
    if not predicted:
        return
    cid = random.choice(predicted)
    with _lock:
        story = _stories.pop(cid, None)
    if story is None:
        return
    decision = random.choices(["approved", "rejected"], weights=[7, 3])[0]
    verb = "approved for action" if decision == "approved" else "rejected"
    event_log.log_event(
        "decision",
        f"Case #{case_code(cid)} — {verb}",
        story.get("location") or story["bank"],
        story["city"],
    )


def _emit_ring_found():
    now = time.time()
    with _lock:
        if now < _next_ring_at[0]:
            return
        _next_ring_at[0] = now + random.uniform(_RING_MIN_INTERVAL_SECONDS, _RING_MAX_INTERVAL_SECONDS)

    from api.rings import _cached_rings

    rings = _cached_rings()
    if not rings:
        return
    r = random.choice(rings)
    cities = r["cities_touched"] or [None]
    event_log.log_event(
        "ring_detected",
        f"Ring R-{r['community_id']:03d} detected",
        f"{r['size']} accounts · {r['num_complaints']} linked complaints",
        random.choice(cities),
    )


def _emit_one():
    # Only among actions actually READY to fire this tick -- each one owns
    # its own pacing (decide/predict are limited by what's really in
    # flight; start/ring by their real-time throttles above). When nothing
    # is ready, this does nothing, silently -- a quiet tick is correct and
    # honest; manufacturing a ring_detected just to have SOMETHING to show
    # is exactly what buried the real case updates before.
    now = time.time()
    with _lock:
        has_predicted = any(s["stage"] == "predicted" for s in _stories.values())
        has_received = any(s["stage"] == "received" for s in _stories.values())
        can_start = now >= _next_new_case_at[0] and len(_stories) < _MAX_ACTIVE_STORIES
        can_ring = now >= _next_ring_at[0]

    actions, weights = [], []
    if has_predicted:
        actions.append("decide")
        weights.append(3)
    if has_received:
        actions.append("predict")
        weights.append(3)
    if can_start and settings_state.get_inject_live_cases():
        actions.append("start")
        weights.append(2)
    if can_ring:
        actions.append("ring")
        weights.append(1)

    if not actions:
        return

    choice = random.choices(actions, weights=weights)[0]
    if choice == "ring":
        _emit_ring_found()
    elif choice == "start":
        _start_story()
    elif choice == "predict":
        _advance_to_prediction()
    elif choice == "decide":
        _advance_to_decision()


def start_simulator():
    """Call once, after the feed/rings caches have already warmed (see
    main.py) -- background daemon thread, never blocks a request."""

    def _loop():
        while True:
            time.sleep(random.uniform(_MIN_INTERVAL_SECONDS, _MAX_INTERVAL_SECONDS))
            try:
                _emit_one()
            except Exception:
                pass  # one bad sample should never kill the loop

    threading.Thread(target=_loop, daemon=True).start()
