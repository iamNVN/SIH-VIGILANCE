"""
replay_state.py -- the live-replay "has this complaint arrived yet" gate,
shared by api/stream.py (owns revealing complaints) and api/feed.py,
api/stats.py (read it to filter Command Center's live-feed view). Split
into its own module so neither of the other two needs to import the
other -- feed.py needs to filter by it, stream.py needs to invalidate
feed.py's cache after revealing one, and putting this in either of those
two would make that a circular import.

Backed by `Complaint.revealed` (a real DB column, not an in-memory cursor)
-- but per explicit product direction, the STARTING POINT it holds is a
session-scoped concept, not persistent history: `reset()` runs
unconditionally on every backend boot (see main.py), pinning the demo back
to a fixed ~INITIAL_REVEALED_TOTAL baseline every time, regardless of how
much got revealed/decided during a previous run. This is a deliberate
choice, not an oversight -- a judge restarting the app should always see
the same clean starting state, not whatever was left over from someone
else's demo five minutes earlier.

Reveals the OLDEST complaints first, per city (not a global cut), so every
investigator's own jurisdiction starts with a real baseline regardless of
which city's complaints happen to be chronologically earliest overall --
same reasoning `advance()` already applies per-reveal, just also applied to
the initial cut.
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Complaint, Victim

# Not "held back until nearly done" (the old design) but "revealed until a
# small nearly-done baseline, the rest arrives live" -- deliberately small
# relative to the dataset's ~690 complaints so there's a large, long-lasting
# pool for Simulate Complaint / the activity simulator to draw from over a
# whole session instead of draining in a few minutes of testing (a real
# reported problem: "top shows all complaints have arrived").
INITIAL_REVEALED_TOTAL = 102


def get_status(db: Session, city: Optional[str] = None) -> dict:
    total_stmt = select(func.count(Complaint.id))
    revealed_stmt = select(func.count(Complaint.id)).where(Complaint.revealed.is_(True))
    if city:
        total_stmt = total_stmt.join(Victim).where(Victim.city == city)
        revealed_stmt = revealed_stmt.join(Victim).where(Victim.city == city)
    total = db.execute(total_stmt).scalar_one()
    revealed = db.execute(revealed_stmt).scalar_one()
    return {"revealed": revealed, "total": total, "done": revealed >= total}


def advance(db: Session, city: Optional[str] = None) -> Optional[Complaint]:
    """Reveals the oldest not-yet-arrived complaint (optionally scoped to
    one city). Returns it, or None if everything (in that scope) has
    already arrived."""
    stmt = select(Complaint).where(Complaint.revealed.is_(False))
    if city:
        stmt = stmt.join(Victim).where(Victim.city == city)
    stmt = stmt.order_by(Complaint.filed_at.asc()).limit(1)
    complaint = db.execute(stmt).scalars().first()
    if complaint is None:
        return None
    complaint.revealed = True
    db.commit()
    db.refresh(complaint)
    return complaint


def reset(db: Session, target_revealed_total: int = INITIAL_REVEALED_TOTAL) -> int:
    """Resets to a fixed starting point: roughly `target_revealed_total`
    complaints revealed -- the OLDEST ones in each city, by filed_at, split
    as evenly across cities as the total allows -- and every other
    complaint held back to arrive "live" afterward, oldest-first, via
    Simulate Complaint or the activity simulator (both call `advance()`,
    unchanged). Also resets `status` back to "open" for every complaint:
    a previous run's investigator decisions are session-scoped right along
    with which complaints had arrived, not independently persistent --
    otherwise a complaint could end up back in "not yet arrived" while
    still carrying a stale "approved"/"rejected" status from before this
    reset, a real inconsistent state worth avoiding outright.

    Called unconditionally on every backend startup (see main.py's
    on_startup) -- not just a manual action -- so nothing revealed or
    decided in a previous run persists across a restart. Returns how many
    complaints ended up revealed.
    """
    db.execute(Complaint.__table__.update().values(revealed=False, status="open"))
    db.commit()

    cities = sorted(db.execute(select(Victim.city).distinct()).scalars().all())
    n_cities = len(cities) or 1
    base = target_revealed_total // n_cities
    remainder = target_revealed_total - base * n_cities

    revealed_count = 0
    for i, city in enumerate(cities):
        per_city_target = base + (1 if i < remainder else 0)  # spread the remainder across the first few cities
        ids = db.execute(
            select(Complaint.id)
            .join(Victim)
            .where(Victim.city == city)
            .order_by(Complaint.filed_at.asc())
            .limit(per_city_target)
        ).scalars().all()
        if ids:
            db.execute(Complaint.__table__.update().where(Complaint.id.in_(ids)).values(revealed=True))
            revealed_count += len(ids)
    db.commit()
    return revealed_count
