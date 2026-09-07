"""
rings.py -- lists detected fraud rings (Louvain communities with >= 3
linked accounts) across the CURRENT full graph, each with real derived
stats: how many complaints touch it, total amount at risk, and where its
cash-outs cluster. This is the second real destination in the sidebar nav
(previously the app only had one) -- an investigator's "what rings are
active right now" view, distinct from a single case's own investigation.

NOT gated by the live-replay watermark (see core/replay_state.py, used by
stats.py/feed.py) -- account/transaction structure is real and fully known
regardless of which individual complaints the demo's "Simulate Complaint"
button has revealed yet. A ring's member accounts don't stop existing
because one of its linked complaints hasn't "arrived" in the live feed.
This does mean a ring's num_complaints/total_amount_at_risk can include
complaints Command Center's other widgets haven't revealed yet -- a
deliberate scope simplification, not an oversight.
"""

import time
from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from core import dataset_provider
from core.db import get_db
from graph_engine.build_graph import build_graph
from graph_engine.community import community_sizes, detect_communities
from models import Complaint

router = APIRouter(tags=["rings"])

_CACHE_TTL_SECONDS = 90  # matches feed.py's TTL -- see that file for why 90s is safe here too
_cache = {"computed_at": 0.0, "rings": []}


def _compute_rings():
    ds = dataset_provider.get_dataset()
    G = build_graph(ds.accounts, ds.transactions, ds.withdrawal_points, ds.withdrawal_events, as_of=None)
    node_to_community = detect_communities(G)
    sizes = community_sizes(node_to_community)

    accounts_by_id = ds.accounts.set_index("id")
    wpoints_by_id = ds.withdrawal_points.set_index("id")

    rings = []
    complaint_to_ring: dict[int, int] = {}
    for community_id, size in sizes.items():
        if size < 3:
            continue

        member_ids = {
            int(n.split("_", 1)[1]) for n, c in node_to_community.items() if c == community_id and n.startswith("acc_")
        }

        tx = ds.transactions[
            ds.transactions["from_account_id"].isin(member_ids) | ds.transactions["to_account_id"].isin(member_ids)
        ]
        we = ds.withdrawal_events[ds.withdrawal_events["account_id"].isin(member_ids)]

        complaint_ids = sorted(set(tx["complaint_id"].dropna().astype(int)) | set(we["complaint_id"].dropna().astype(int)))
        if not complaint_ids:
            continue

        linked = ds.complaints[ds.complaints["id"].isin(complaint_ids)]
        total_amount = float(linked["amount_lost"].sum())

        cities = [
            wpoints_by_id.loc[pid, "city"]
            for pid in we["withdrawal_point_id"].dropna().astype(int)
            if pid in wpoints_by_id.index
        ]
        top_city = Counter(cities).most_common(1)[0][0] if cities else None
        cities_touched = sorted(set(cities))

        banks = [
            accounts_by_id.loc[aid, "bank_name"]
            for aid in member_ids
            if aid in accounts_by_id.index
        ]
        top_bank = Counter(banks).most_common(1)[0][0] if banks else None

        last_activity = None
        if len(tx) > 0:
            last_activity = tx["timestamp"].max()
        if len(we) > 0:
            we_max = we["timestamp"].max()
            last_activity = we_max if last_activity is None else max(last_activity, we_max)

        rings.append({
            "community_id": int(community_id),
            "size": size,
            "num_complaints": len(complaint_ids),
            "total_amount_at_risk": total_amount,
            "top_city": top_city,
            "cities_touched": cities_touched,
            "top_bank": top_bank,
            "last_activity": last_activity.isoformat() if last_activity is not None else None,
            "sample_complaint_id": complaint_ids[0],
            # Full id list + earliest filed date -- cheap here (already
            # have `linked` in memory from the total_amount sum above), and
            # is what the ring detail page needs: every linked case, and
            # when the first one that ties into this ring was actually
            # filed (not when the graph happened to be recomputed).
            "complaint_ids": complaint_ids,
            "first_filed_at": linked["filed_at"].min().isoformat(),
        })
        for cid in complaint_ids:
            complaint_to_ring[cid] = int(community_id)

    rings.sort(key=lambda r: r["total_amount_at_risk"], reverse=True)
    return rings, complaint_to_ring


def _cached_rings():
    now = time.time()
    if now - _cache["computed_at"] < _CACHE_TTL_SECONDS:
        return _cache["rings"]
    rings, complaint_to_ring = _compute_rings()
    _cache.update({"computed_at": now, "rings": rings, "complaint_to_ring": complaint_to_ring})
    return rings


def get_ring_for_complaint(complaint_id: int) -> Optional[dict]:
    """complaint_id -> the ring it belongs to, or None -- used by stream.py
    to log a real "linked to ring" event on reveal (see core/event_log.py),
    cross-referenced against this same computed structure, not a separate
    guess."""
    _cached_rings()  # ensure _cache["complaint_to_ring"] is populated
    community_id = _cache.get("complaint_to_ring", {}).get(complaint_id)
    if community_id is None:
        return None
    for r in _cache["rings"]:
        if r["community_id"] == community_id:
            return r
    return None


_startup_logged = [False]


def log_initial_ring_detections():
    """Called once from main.py's startup pre-warm thread -- logs one real
    event per detected ring (its actual size/complaint count) so Command
    Center's Live Investigation Feed has real initial content instead of
    starting empty. Guarded so this never re-fires on this cache's normal
    periodic refresh -- the underlying account/transaction graph doesn't
    change during a session (see this file's module docstring), so there's
    no genuine "newly detected" moment to log beyond the first one."""
    if _startup_logged[0]:
        return
    _startup_logged[0] = True
    from core import event_log

    for r in _cached_rings():
        for city in r["cities_touched"] or [None]:
            event_log.log_event(
                "ring_detected",
                f"Ring R-{r['community_id']:03d} detected",
                f"{r['size']} accounts · {r['num_complaints']} linked complaints",
                city,
            )


@router.get("/rings")
def list_rings(limit: int = 50, city: Optional[str] = None):
    rings = _cached_rings()
    if city:
        rings = [r for r in rings if city in r["cities_touched"]]
    return {"rings": rings[: min(limit, 200)]}


@router.get("/rings/{community_id}")
def get_ring(community_id: int, db: Session = Depends(get_db)):
    rings = _cached_rings()
    ring = next((r for r in rings if r["community_id"] == community_id), None)
    if ring is None:
        raise HTTPException(404, f"ring {community_id} not found (it may be below the 3-account threshold)")

    # Real complaint rows for every id this ring touches -- only fetched
    # here (not in _compute_rings(), which runs for every ring on every
    # cache refresh whether or not anyone's looking at it) since this is
    # the one place that actually needs full victim/bank/status detail per
    # case, not just the id.
    from .complaints import _to_out

    rows = (
        db.query(Complaint)
        .options(joinedload(Complaint.victim))
        .filter(Complaint.id.in_(ring["complaint_ids"]))
        .order_by(Complaint.filed_at.asc())
        .all()
    )
    return {**ring, "linked_complaints": [_to_out(c) for c in rows]}
