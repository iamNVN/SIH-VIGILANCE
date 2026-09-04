"""
feed.py -- a cross-case top-1 prediction feed (no per-candidate SHAP explain,
unlike /predict/{id} -- this batches over many complaints, so it deliberately
skips the expensive explanation step and just returns the single top-ranked
call to action for each). Backs two sidebar views: Alerts (HIGH urgency only)
and Predictions (the full ranked feed) -- both real model output, cached
briefly like /stats and /rings.
"""

import threading
import time
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import dataset_provider, replay_state
from core.db import SessionLocal
from core.model_registry import registry
from graph_engine.features import ADVANCED_FEATURE_COLUMNS, build_candidate_features
from models import Complaint

from .predict import _complaint_row, lift_urgency

router = APIRouter(tags=["feed"])

_CACHE_TTL_SECONDS = 30
_cache = {"computed_at": 0.0, "feed": []}
# Command Center's first load fires several requests that all depend on
# this same feed (stats' high_risk_cases, hotspots, alerts, predictions)
# roughly simultaneously. Without a lock, a cold cache means each of those
# independently pays the full ~5-6s batch-scoring cost in parallel instead
# of one paying it while the rest wait -- verified: this is exactly what
# made Command Center's cards/panels appear at wildly different times on
# first load.
_lock = threading.Lock()


def _compute_feed(limit_complaints: int = 150):
    if not registry.ready:
        raise HTTPException(503, "models not trained yet -- run `python -m ml.train` first")

    db: Session = SessionLocal()
    try:
        watermark = replay_state.get_live_watermark(db)
        complaints = db.execute(
            select(Complaint)
            .where(Complaint.status == "open", Complaint.filed_at <= watermark)
            .order_by(Complaint.filed_at.desc())
            .limit(limit_complaints)
        ).scalars().all()
        if not complaints:
            return []

        ds = dataset_provider.get_dataset()

        # A dashboard feed wants "best prediction right now", not a frozen
        # point-in-time snapshot from when each complaint happened to be
        # filed (that discipline is for evaluate.py's accuracy measurement,
        # not this view). Sharing ONE as_of across the whole batch also means
        # graph_cache builds the graph+communities once instead of once per
        # complaint -- with N distinct as_of values this endpoint measured
        # 30s+ and counting for just 10 complaints; with one shared value the
        # first call pays the graph-build cost and the rest are cache hits.
        batch_as_of = max(c.filed_at for c in complaints)

        items = []
        for complaint in complaints:
            complaint_row = _complaint_row(complaint)
            complaint_row["filed_at"] = pd.Timestamp(batch_as_of)
            try:
                candidates = build_candidate_features(ds, complaint_row)
            except Exception:
                continue
            if candidates.empty:
                continue

            candidates["advanced_prob"] = registry.advanced_calibrated.predict_proba(candidates[ADVANCED_FEATURE_COLUMNS])[:, 1]
            top = candidates.sort_values("advanced_prob", ascending=False).iloc[0]
            confidence = float(top["advanced_prob"])
            n_candidates = len(candidates)

            items.append({
                "complaint_id": complaint.id,
                "victim_name": complaint.victim.name_fake if complaint.victim else None,
                "victim_city": complaint.victim.city if complaint.victim else None,
                "bank_name": complaint.bank_name,
                "amount_lost": complaint.amount_lost,
                "filed_at": complaint.filed_at.isoformat(),
                "top_prediction": {
                    "name": top["name"],
                    "lat": float(top["lat"]),
                    "lon": float(top["lon"]),
                    "confidence": round(confidence, 4),
                    "n_candidates": n_candidates,
                    "urgency": lift_urgency(confidence, n_candidates),
                },
            })

        items.sort(key=lambda it: it["top_prediction"]["confidence"], reverse=True)
        return items
    finally:
        db.close()


def _cached_feed():
    now = time.time()
    if now - _cache["computed_at"] < _CACHE_TTL_SECONDS:
        return _cache["feed"]

    with _lock:
        # Re-check inside the lock: whoever was first through already
        # refreshed the cache while we were waiting for it.
        now = time.time()
        if now - _cache["computed_at"] < _CACHE_TTL_SECONDS:
            return _cache["feed"]
        feed = _compute_feed()
        _cache.update({"computed_at": time.time(), "feed": feed})
        return feed


def cached_feed_if_warm():
    """Like `_cached_feed()` but never triggers the expensive computation --
    returns the cached feed if it's fresh, else None. For callers (like
    /stats) that want this data ONLY if it's already cheap to get."""
    if time.time() - _cache["computed_at"] < _CACHE_TTL_SECONDS:
        return _cache["feed"]
    return None


def invalidate_feed_cache():
    """Called by stream.py right after Simulate Complaint reveals one --
    without this, the dashboard would keep showing the pre-reveal state for
    up to _CACHE_TTL_SECONDS, making the button feel like it did nothing."""
    _cache["computed_at"] = 0.0


@router.get("/feed/predictions")
def predictions_feed(limit: int = 40, city: Optional[str] = None):
    items = _cached_feed()
    if city:
        items = [it for it in items if it["victim_city"] == city]
    return {"items": items[: min(limit, 100)]}


@router.get("/feed/alerts")
def alerts_feed(limit: int = 40, city: Optional[str] = None, sort: str = "confidence"):
    items = _cached_feed()
    if city:
        items = [it for it in items if it["victim_city"] == city]
    high = [it for it in items if it["top_prediction"]["urgency"] == "HIGH"]
    if sort == "recent":
        # Command Center's "Recent High Risk Complaints" preview means
        # recent, not "the model's single most confident calls" (the
        # default -- what the dedicated Alerts page wants).
        high = sorted(high, key=lambda it: it["filed_at"], reverse=True)
    # `total` is the real, complete HIGH-urgency count before slicing to
    # `limit` -- Command Center's "High Risk Cases" stat card uses this
    # (this endpoint's own fetch, already happening for the alerts table)
    # rather than a second, separate count.
    return {"items": high[: min(limit, 100)], "total": len(high)}
