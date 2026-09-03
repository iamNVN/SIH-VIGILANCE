"""
feed.py -- a cross-case top-1 prediction feed (no per-candidate SHAP explain,
unlike /predict/{id} -- this batches over many complaints, so it deliberately
skips the expensive explanation step and just returns the single top-ranked
call to action for each). Backs two sidebar views: Alerts (HIGH urgency only)
and Predictions (the full ranked feed) -- both real model output, cached
briefly like /stats and /rings.
"""

import time
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import dataset_provider
from core.db import SessionLocal
from core.model_registry import registry
from graph_engine.features import ADVANCED_FEATURE_COLUMNS, build_candidate_features
from models import Complaint

from .predict import _complaint_row

router = APIRouter(tags=["feed"])

_CACHE_TTL_SECONDS = 30
_cache = {"computed_at": 0.0, "feed": []}


def _lift_urgency(confidence: float, n_candidates: int) -> str:
    # Raw confidence rarely crosses 50% here (see Analytics -- Precision@1 is
    # real and modest), so classifying urgency by absolute confidence would
    # make this feed permanently empty. Lift over random chance among this
    # complaint's own candidates is the honest, comparable signal across
    # cases with different candidate-set sizes.
    if n_candidates <= 0:
        return "LOW"
    lift = confidence / (1 / n_candidates)
    if lift >= 5:
        return "HIGH"
    if lift >= 2:
        return "MEDIUM"
    return "LOW"


def _compute_feed(limit_complaints: int = 150):
    if not registry.ready:
        raise HTTPException(503, "models not trained yet -- run `python -m ml.train` first")

    db: Session = SessionLocal()
    try:
        complaints = db.execute(
            select(Complaint).where(Complaint.status == "open").order_by(Complaint.filed_at.desc()).limit(limit_complaints)
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
                    "confidence": round(confidence, 4),
                    "n_candidates": n_candidates,
                    "urgency": _lift_urgency(confidence, n_candidates),
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
    feed = _compute_feed()
    _cache.update({"computed_at": now, "feed": feed})
    return feed


@router.get("/feed/predictions")
def predictions_feed(limit: int = 40, city: Optional[str] = None):
    items = _cached_feed()
    if city:
        items = [it for it in items if it["victim_city"] == city]
    return {"items": items[: min(limit, 100)]}


@router.get("/feed/alerts")
def alerts_feed(limit: int = 40, city: Optional[str] = None):
    items = _cached_feed()
    if city:
        items = [it for it in items if it["victim_city"] == city]
    high = [it for it in items if it["top_prediction"]["urgency"] == "HIGH"]
    return {"items": high[: min(limit, 100)]}
