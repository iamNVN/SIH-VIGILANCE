"""
stats.py -- lightweight summary numbers for the Command Center screen
(Blueprint Section 12 screen 1: "today's stats, active-ring count").

Community detection over the full current graph takes a second or two
(Louvain + graph construction) -- too slow to redo on every dashboard poll,
so the result is cached for a short window. This endpoint is deliberately
cheap and simple: the frontend just displays these numbers, no client-side
computation.

Accepts an optional `city` filter -- this is what makes an investigator's
Command Center actually show THEIR jurisdiction's numbers instead of the
national total (see auth/AuthContext.jsx's per-persona `city`). Enforced
here server-side, not just hidden in the UI, so it's a real scope rather
than a cosmetic one -- though see that file's docstring: the persona itself
is still self-declared, not authenticated, so this is jurisdiction-scoped
DATA ACCESS for a demo, not production-grade security.
"""

import time
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.db import get_db
from models import Complaint, Victim

from .rings import _cached_rings

router = APIRouter(tags=["stats"])

_CACHE_TTL_SECONDS = 30
_ring_cache = {"computed_at": 0.0, "active": 0, "largest": 0}


def _active_rings_all():
    now = time.time()
    if now - _ring_cache["computed_at"] < _CACHE_TTL_SECONDS:
        return _ring_cache["active"], _ring_cache["largest"]

    rings = _cached_rings()
    _ring_cache.update({
        "computed_at": now,
        "active": len(rings),
        "largest": max((r["size"] for r in rings), default=0),
    })
    return _ring_cache["active"], _ring_cache["largest"]


def _active_rings_for_city(city: str):
    rings = [r for r in _cached_rings() if city in r["cities_touched"]]
    return len(rings), max((r["size"] for r in rings), default=0)


@router.get("/stats")
def get_stats(city: Optional[str] = None, db: Session = Depends(get_db)):
    count_stmt = select(func.count(Complaint.id))
    amount_stmt = select(func.coalesce(func.sum(Complaint.amount_lost), 0.0)).where(Complaint.status == "open")
    open_stmt = select(func.count(Complaint.id)).where(Complaint.status == "open")
    if city:
        count_stmt = count_stmt.join(Victim).where(Victim.city == city)
        amount_stmt = amount_stmt.join(Victim).where(Victim.city == city)
        open_stmt = open_stmt.join(Victim).where(Victim.city == city)

    total_complaints = db.execute(count_stmt).scalar_one()
    open_count = db.execute(open_stmt).scalar_one()
    total_amount_at_risk = db.execute(amount_stmt).scalar_one()

    if city:
        total_victims = db.execute(select(func.count(Victim.id)).where(Victim.city == city)).scalar_one()
        active_rings, largest_ring_size = _active_rings_for_city(city)
    else:
        total_victims = db.execute(select(func.count(Victim.id))).scalar_one()
        active_rings, largest_ring_size = _active_rings_all()

    return {
        "total_complaints": total_complaints,
        "total_victims": total_victims,
        "open_complaints": open_count,
        "total_amount_at_risk": total_amount_at_risk,
        "suspected_active_rings": active_rings,
        "largest_ring_size": largest_ring_size,
        "scope": city or "national",
    }
