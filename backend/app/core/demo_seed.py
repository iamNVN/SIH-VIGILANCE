"""demo_seed.py -- seeds a small, fixed set of investigator decisions at
every backend startup, so a fresh demo boot doesn't show an empty Audit
Trail (a real reported gap: core/event_log.py is in-memory, same as the
rest of live-replay state -- see replay_state.py's docstring -- so it
starts genuinely empty on every restart otherwise).

NOT FABRICATED DATA: each seeded decision runs a real, already-revealed
complaint's real cached prediction through api.complaints.apply_decision()
-- the exact same function the real investigator-facing /decision endpoint
calls. Same DB status change, same feed removal, same event log entry.
The only thing "seeded" here is that a person didn't click the button;
everywhere else in the app (Cases, Command Center, /stats, Audit Trail)
a seeded decision is indistinguishable from a real one -- same idea as
core/activity_simulator.py's ongoing simulated decisions, just applied
once at boot instead of waiting for the simulator to organically produce
a few over a session.

Picks the first N items off the already-warm cached feed (deterministic --
same complaints every boot, not randomized), so the demo's starting state
is reproducible run to run.
"""

from sqlalchemy.orm import Session

from models import Complaint

_N_APPROVED = 3
_N_REJECTED = 2


def seed_initial_decisions(db: Session):
    from api.complaints import apply_decision
    from api.feed import cached_feed_if_warm

    items = cached_feed_if_warm() or []
    if not items:
        return  # feed cache never warmed (models not ready) -- nothing to seed against

    to_approve = items[:_N_APPROVED]
    to_reject = items[_N_APPROVED : _N_APPROVED + _N_REJECTED]

    for it in to_approve:
        complaint = db.get(Complaint, it["complaint_id"])
        if complaint is not None:
            apply_decision(db, complaint, "approved")
    for it in to_reject:
        complaint = db.get(Complaint, it["complaint_id"])
        if complaint is not None:
            apply_decision(db, complaint, "rejected")
