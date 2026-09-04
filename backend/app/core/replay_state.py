"""
replay_state.py -- the live-replay "has this complaint arrived yet" gate,
shared by api/stream.py (owns revealing complaints) and api/feed.py,
api/stats.py (read it to filter Command Center's live-feed view). Split
into its own module so neither of the other two needs to import the
other -- feed.py needs to filter by it, stream.py needs to invalidate
feed.py's cache after revealing one, and putting this in either of those
two would make that a circular import.

Backed by `Complaint.revealed` (a real column, not an in-memory cursor --
see models/orm.py and scripts/seed_db.py) so it survives backend restarts
and supports per-city reveals: seed_db.py holds back the most recent
HOLDBACK_PER_CITY complaints IN EACH CITY (not one global holdback), so
"Simulate Complaint" always has something in ANY investigator's own
jurisdiction to reveal, not just whichever city the globally-next
complaint happens to be in. Cases/search/direct case links are
deliberately NOT gated (see api/complaints.py) -- that's the full-archive
investigator tool, not the "live feed" view.
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Complaint, Victim


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


def reset(db: Session, holdback_per_city: int = 15) -> int:
    """Restores the original demo starting point: the most recent
    `holdback_per_city` complaints in each city go back to un-arrived,
    everything else is marked arrived. Returns how many were held back."""
    db.execute(Complaint.__table__.update().values(revealed=True))
    db.commit()

    cities = db.execute(select(Victim.city).distinct()).scalars().all()
    holdback_count = 0
    for city in cities:
        ids = db.execute(
            select(Complaint.id)
            .join(Victim)
            .where(Victim.city == city)
            .order_by(Complaint.filed_at.desc())
            .limit(holdback_per_city)
        ).scalars().all()
        if ids:
            db.execute(Complaint.__table__.update().where(Complaint.id.in_(ids)).values(revealed=False))
            holdback_count += len(ids)
    db.commit()
    return holdback_count
