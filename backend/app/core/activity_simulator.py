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
replay_state.INITIAL_REVEALED_TOTAL complaints are revealed at boot, the
rest held back -- see replay_state.reset(), which runs on every backend
startup), this is rate-limited to roughly once every 24s
(_NEW_CASE_MIN/MAX_INTERVAL_SECONDS), not the few-second cadence the other
event types use, and gated by core/settings_state.py's "Inject Live Cases"
toggle (Settings page) -- OFF means no automatic injection at all; a real
investigator's own Simulate Complaint click is unaffected either way.

Prediction/decision events still sample real cached data (a real
complaint's real cached prediction) on the faster cadence -- those were
never the part that needed slowing down or gating.

EACH CASE TELLS ONE COHERENT STORY, NOT THREE UNRELATED SAMPLES
-------------------------------------------------------------------
`_stories` tracks complaints actually moving through
received -> predicted -> decided, so the SAME case id (and, once
predicted, the SAME predicted location) shows up consistently across that
case's own events, the way a real investigation would read -- not an
unrelated random complaint sampled fresh for each event type.

NO RING GETS ANNOUNCED TWICE
-------------------------------------------------------------------
main.py's startup already announces EVERY real ring once
(rings.py's log_initial_ring_detections()) -- there is no genuinely NEW
ring to find afterward on a STATIC graph, so re-announcing one on a timer
isn't "keeping the feed alive," it's just replaying an old announcement
(verified live: this was producing byte-identical repeated "Ring R-0xx
detected" entries). Ongoing ring announcements are removed here entirely
rather than deduplicated, since there was never a second real
ring-detection moment to report.

A NEAR-DUPLICATE PREDICTION EVENT IS STILL POSSIBLE, AND THAT'S HANDLED IN event_log.py
-------------------------------------------------------------------
`_advance_to_prediction()` only fires once per story (each cid is removed
from the "received" pool the instant it flips to "predicted", under the
same lock that checks its stage), and `_start_story()` can never re-pick
an already-revealed complaint (replay_state.advance() only ever returns
one that's still unrevealed). But a REAL /predict/{id} call (an
investigator opening that exact case in the UI while it's also mid-story
here) can independently log its own "Cash-out prediction generated" event
for the same complaint around the same time -- two genuinely different,
individually real log calls that read as a confusing duplicate in the
feed. core/event_log.py's log_event() is where that's deduplicated (by
type+message within a short window), not here, since the same collision
is possible between any two real callers, not just this simulator.

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
# Higher than before (6) -- at ~2.5 new cases/minute, a story now starts
# roughly every 24s on average, so a low cap would fill up and start
# silently throttling new arrivals well before predict/decide have had a
# chance to work through the backlog.
_MAX_ACTIVE_STORIES = 15

# ~2.5 complaints/minute average (24s), per explicit product direction --
# was 3-4 minutes, which combined with a small (75-complaint) held-back
# pool drained out entirely within a single testing session ("top shows
# all complaints have arrived"). The pool this now draws from is much
# larger (~588 of ~690 complaints held back at startup, see
# replay_state.INITIAL_REVEALED_TOTAL), so this cadence can run for a full
# multi-hour session without exhausting it, and a full backend restart
# resets the pool anyway.
_NEW_CASE_MIN_INTERVAL_SECONDS = 18
_NEW_CASE_MAX_INTERVAL_SECONDS = 30

# complaint_id -> {"stage": "received"|"predicted", "city": str|None,
# "location": str|None, "confidence": float|None} -- in-memory, one
# process's worth of "which simulated cases are mid-story right now".
_stories: dict[int, dict] = {}
_lock = threading.Lock()
# Own throttle for real injections specifically, separate from the general
# _emit_one() tick -- re-rolled after each real injection so the next one
# is again ~24s out, not a fixed schedule.
_next_new_case_at = [0.0]


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
        #
        # replay_state.advance() only ever hands back a genuinely
        # not-yet-revealed complaint, so this can't collide with a
        # currently-active or already-completed simulated story -- those
        # are all already-revealed complaints by definition.
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


def _emit_one():
    # Only among actions actually READY to fire this tick -- each one owns
    # its own pacing (decide/predict are limited by what's really in
    # flight; start by its own real-time throttle above). When nothing is
    # ready, this does nothing, silently -- a quiet tick is correct and
    # honest.
    now = time.time()
    with _lock:
        has_predicted = any(s["stage"] == "predicted" for s in _stories.values())
        has_received = any(s["stage"] == "received" for s in _stories.values())
        can_start = now >= _next_new_case_at[0] and len(_stories) < _MAX_ACTIVE_STORIES

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

    if not actions:
        return

    choice = random.choices(actions, weights=weights)[0]
    if choice == "start":
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
