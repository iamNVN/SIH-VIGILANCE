"""
activity_simulator.py -- keeps Command Center's Live Investigation Feed
populated between real user actions.

The underlying dataset is a static historical replay (see
dataset_provider.py's docstring) -- there's no genuine continuous stream of
new real-world activity to log, so an event-driven-only feed (stream.py's
reveal, a real /predict call, complaints.py's /decision) sits empty almost
all the time. Per explicit product direction, this fills that gap: every
few seconds it emits ONE event, always built from REAL sampled data --
a real complaint's real amount/city, a real cached prediction's real
location/confidence, a real detected ring's real size/complaint count.
Only the CADENCE is synthetic (there's no real clock behind "right now, a
complaint arrived"), never the numbers inside an event. Real events from
actual user actions log on top of this, indistinguishable in the feed.

The one type with no real-data anchor is the simulated decision
(approve/reject) -- it does NOT write to the complaint's actual `status`
(that only happens through complaints.py's real, investigator-triggered
/decision endpoint). It borrows a real complaint id/bank/city for the
message so it reads as concretely as the others, without quietly mutating
case state nobody asked to change.
"""

import random
import threading
import time
from typing import Optional

from sqlalchemy import select

from core import event_log
from core.db import SessionLocal
from models import Complaint

_MIN_INTERVAL_SECONDS = 4
_MAX_INTERVAL_SECONDS = 10
_TYPE_WEIGHTS = {"new_case": 3, "prediction": 3, "ring_found": 1, "decision": 2}


def _pick_random_open_complaint(db) -> Optional[Complaint]:
    ids = db.execute(select(Complaint.id).where(Complaint.status == "open", Complaint.revealed.is_(True))).scalars().all()
    if not ids:
        return None
    return db.get(Complaint, random.choice(ids))


def _emit_new_case(db):
    c = _pick_random_open_complaint(db)
    if c is None:
        return
    city = c.victim.city if c.victim else None
    event_log.log_event(
        "complaint_received",
        "New complaint received",
        f"₹{c.amount_lost:,.0f} · {city or 'Unknown city'}",
        city,
    )


def _emit_prediction():
    from api.feed import cached_feed_if_warm

    items = cached_feed_if_warm() or []
    if not items:
        return
    it = random.choice(items)
    tp = it["top_prediction"]
    event_log.log_event(
        "prediction_generated",
        "Cash-out prediction generated",
        f"{tp['name']} · {round(tp['confidence'] * 100, 1)}%",
        it["victim_city"],
    )


def _emit_ring_found():
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


def _emit_decision(db):
    c = _pick_random_open_complaint(db)
    if c is None:
        return
    city = c.victim.city if c.victim else None
    decision = random.choices(["approved", "rejected"], weights=[7, 3])[0]
    verb = "approved for action" if decision == "approved" else "rejected"
    event_log.log_event("decision", f"Case #{c.id} {verb}", c.bank_name, city)


def _emit_one():
    choice = random.choices(list(_TYPE_WEIGHTS), weights=list(_TYPE_WEIGHTS.values()))[0]
    if choice == "prediction":
        _emit_prediction()
        return
    if choice == "ring_found":
        _emit_ring_found()
        return
    db = SessionLocal()
    try:
        if choice == "new_case":
            _emit_new_case(db)
        elif choice == "decision":
            _emit_decision(db)
    finally:
        db.close()


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
