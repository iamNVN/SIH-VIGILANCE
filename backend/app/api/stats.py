"""
stats.py -- lightweight summary numbers for the Command Center screen
(Blueprint Section 12 screen 1: "today's stats, active-ring count").

Community detection over the full current graph takes a second or two
(Louvain + graph construction) -- too slow to redo on every dashboard poll,
so the result is cached for a short window. This endpoint is deliberately
cheap and simple: the frontend just displays these numbers, no client-side
computation.
"""

import time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core import dataset_provider
from core.db import get_db
from graph_engine.build_graph import build_graph
from graph_engine.community import community_sizes, detect_communities
from models import Complaint, Victim

router = APIRouter(tags=["stats"])

_CACHE_TTL_SECONDS = 30
_cache = {"computed_at": 0.0, "active_rings": 0, "largest_ring_size": 0}


def _active_rings():
    now = time.time()
    if now - _cache["computed_at"] < _CACHE_TTL_SECONDS:
        return _cache["active_rings"], _cache["largest_ring_size"]

    ds = dataset_provider.get_dataset()
    G = build_graph(ds.accounts, ds.transactions, ds.withdrawal_points, ds.withdrawal_events, as_of=None)
    sizes = community_sizes(detect_communities(G))
    active = [s for s in sizes.values() if s >= 3]  # a "ring" needs at least a couple of linked accounts, not a lone pair

    _cache.update({
        "computed_at": now,
        "active_rings": len(active),
        "largest_ring_size": max(active) if active else 0,
    })
    return _cache["active_rings"], _cache["largest_ring_size"]


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_complaints = db.execute(select(func.count(Complaint.id))).scalar_one()
    total_victims = db.execute(select(func.count(Victim.id))).scalar_one()
    total_amount_at_risk = db.execute(
        select(func.coalesce(func.sum(Complaint.amount_lost), 0.0)).where(Complaint.status == "open")
    ).scalar_one()
    open_count = db.execute(select(func.count(Complaint.id)).where(Complaint.status == "open")).scalar_one()

    active_rings, largest_ring_size = _active_rings()

    return {
        "total_complaints": total_complaints,
        "total_victims": total_victims,
        "open_complaints": open_count,
        "total_amount_at_risk": total_amount_at_risk,
        "suspected_active_rings": active_rings,
        "largest_ring_size": largest_ring_size,
    }
