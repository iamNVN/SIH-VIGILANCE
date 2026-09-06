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
from collections import defaultdict
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.db import get_db
from models import Complaint, Victim

from .feed import _cached_feed, cached_feed_if_warm
from .predict import predictions_served_today
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


def _high_risk_case_count(city: Optional[str]) -> Optional[int]:
    # Non-blocking: /stats must stay cheap (it's on Command Center's
    # critical render path). If the ~150-complaint batch feed hasn't been
    # computed recently by someone else (Alerts/Predictions/hotspots), this
    # returns None rather than paying that cost itself -- the frontend
    # shows this one card as "loading" for the ~5s it takes the OTHER
    # feed-backed panel to populate the cache, instead of every stat on
    # the page stalling behind it.
    items = cached_feed_if_warm()
    if items is None:
        return None
    if city:
        items = [it for it in items if it["victim_city"] == city]
    return sum(1 for it in items if it["top_prediction"]["urgency"] == "HIGH")


@router.get("/stats")
def get_stats(city: Optional[str] = None, db: Session = Depends(get_db)):
    # Command Center's "Total Complaints" headline number is the full case
    # count for the jurisdiction (same number Cases shows) -- an
    # investigator reading this as "how many cases exist" would find a
    # number gated to only what's "arrived" in the replay misleadingly low
    # (a real reported confusion: 20 here vs 40+ on Cases for the same
    # city). Open/at-risk stay scoped to `revealed` -- those describe the
    # live, currently-actionable queue, not the archive size.
    count_stmt = select(func.count(Complaint.id))
    amount_stmt = select(func.coalesce(func.sum(Complaint.amount_lost), 0.0)).where(
        Complaint.status == "open", Complaint.revealed.is_(True)
    )
    open_stmt = select(func.count(Complaint.id)).where(Complaint.status == "open", Complaint.revealed.is_(True))
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
        # Real count of open cases whose top prediction clears the same
        # 5x-lift-over-chance bar as Alerts/urgency badges elsewhere -- not
        # a separate invented definition of "high risk." null if the batch
        # feed isn't warm yet (frontend falls back to /feed/alerts' own
        # `total`, which it's fetching anyway for the alerts table).
        "high_risk_cases": _high_risk_case_count(city),

        # A real, honestly-scoped usage counter (see predict.py) -- resets
        # on backend restart, counts real wall-clock "today," not the
        # dataset's fictional complaint dates.
        "predictions_today": predictions_served_today(),
        "scope": city or "national",
    }


@router.get("/stats/timeseries")
def get_timeseries(days: int = 7, city: Optional[str] = None, db: Session = Depends(get_db)):
    """Daily complaint volume for the most recent `days` calendar dates
    PRESENT IN THE DATA (the dataset's complaints are fictionally dated
    June-Aug 2026, not real "today" -- see core/dataset_provider.py), plus
    how many of each day's complaints are currently scored HIGH risk. The
    high-risk count is only as complete as the cached feed's own coverage
    (the `n most recent open complaints` it batches over, see feed.py) --
    real numbers, just not an exhaustive per-day audit for very old dates.
    """
    stmt = select(Complaint.filed_at, Complaint.id).where(Complaint.revealed.is_(True))
    if city:
        stmt = stmt.join(Victim).where(Victim.city == city)
    rows = db.execute(stmt).all()
    if not rows:
        return {"days": []}

    latest_date = max(r.filed_at for r in rows).date()
    date_keys = [(latest_date - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    total_by_day = defaultdict(int)
    for row in rows:
        total_by_day[row.filed_at.date().isoformat()] += 1

    feed_items = _cached_feed()
    if city:
        feed_items = [it for it in feed_items if it["victim_city"] == city]
    high_risk_by_day = defaultdict(int)
    for it in feed_items:
        if it["top_prediction"]["urgency"] == "HIGH":
            day_key = it["filed_at"][:10]
            high_risk_by_day[day_key] += 1

    return {
        "days": [
            {"date": d, "total_complaints": total_by_day.get(d, 0), "high_risk_complaints": high_risk_by_day.get(d, 0)}
            for d in date_keys
        ]
    }


@router.get("/stats/hotspots")
def get_hotspots(limit: int = 5, city: Optional[str] = None):
    """Top predicted cash-out locations aggregated ACROSS currently open
    cases (not one case's own top-5 -- that's /predict/{id}). Share % is a
    real, computed fraction of how often each location is some case's top
    pick within the cached feed -- never a fabricated number."""
    items = _cached_feed()
    if city:
        items = [it for it in items if it["victim_city"] == city]
    if not items:
        return {"hotspots": [], "n_cases": 0}

    by_location: dict[str, dict] = {}
    for it in items:
        tp = it["top_prediction"]
        key = tp["name"]
        if key not in by_location:
            by_location[key] = {"name": tp["name"], "lat": tp["lat"], "lon": tp["lon"], "count": 0}
        by_location[key]["count"] += 1

    total = len(items)
    hotspots = sorted(by_location.values(), key=lambda h: h["count"], reverse=True)[: min(limit, 20)]
    for h in hotspots:
        h["share_pct"] = round(100 * h["count"] / total, 1)

    return {"hotspots": hotspots, "n_cases": total}
