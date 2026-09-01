"""
predict.py -- top-5 ranked cash-out prediction endpoint, Blueprint Section
4/11. Output matches Section 11's exact JSON contract.

`as_of` for feature construction is the complaint's own `filed_at` -- "what
could the system have known at the moment this complaint was filed" (same
point-in-time discipline as ml/evaluate.py, see graph_engine/build_graph.py's
module docstring). This is also the operationally correct choice: prediction
should happen at intake time, not at the real wall-clock "now" (which for
this synthetic dataset's June-August 2026 window is meaningless -- see
core/dataset_provider.py's docstring).
"""

from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core import dataset_provider
from core.db import get_db
from core.model_registry import registry
from graph_engine.features import ADVANCED_FEATURE_COLUMNS, BASELINE_FEATURE_COLUMNS, build_candidate_features
from ml import explain as shap_explain
from models import Complaint, WithdrawalEvent

router = APIRouter(tags=["predict"])

TOP_K = 5


def _complaint_row(complaint: Complaint) -> pd.Series:
    return pd.Series({
        "id": complaint.id,
        "victim_id": complaint.victim_id,
        "filed_at": pd.Timestamp(complaint.filed_at),
        "amount_lost": complaint.amount_lost,
        "bank_name": complaint.bank_name,
    })


def _urgency(rank: int, confidence: float) -> str:
    if rank == 1 and confidence >= 0.5:
        return "HIGH"
    if rank <= 2:
        return "MEDIUM"
    return "LOW"


@router.post("/predict/{complaint_id}")
def predict(complaint_id: int, db: Session = Depends(get_db)):
    if not registry.ready:
        raise HTTPException(503, "models not trained yet -- run `python -m ml.train` first")

    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(404, f"complaint {complaint_id} not found")

    ds = dataset_provider.get_dataset()
    complaint_row = _complaint_row(complaint)
    candidates = build_candidate_features(ds, complaint_row)

    candidates["baseline_prob"] = registry.baseline_calibrated.predict_proba(candidates[BASELINE_FEATURE_COLUMNS])[:, 1]
    candidates["advanced_prob"] = registry.advanced_calibrated.predict_proba(candidates[ADVANCED_FEATURE_COLUMNS])[:, 1]
    candidates = candidates.sort_values("advanced_prob", ascending=False).reset_index(drop=True)

    top = candidates.head(TOP_K)
    predictions = []
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        explanation = shap_explain.explain_row(registry.advanced_raw, ADVANCED_FEATURE_COLUMNS, row)
        narrative = shap_explain.narrative_from_explanation(
            explanation, int(row["community_size"]), int(row["community_num_complaints"])
        )
        confidence = float(row["advanced_prob"])
        predictions.append({
            "rank": rank,
            "withdrawal_point_id": int(row["withdrawal_point_id"]),
            "name": row["name"],
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "confidence": round(confidence, 4),
            "estimated_window": {
                "earliest": complaint.filed_at.isoformat(),
                "latest": (complaint.filed_at).isoformat(),
            },
            "amount_at_risk": float(complaint.amount_lost),
            "connected_entities": [],
            "explanation": {
                "top_features": explanation["top_features"],
                "narrative": narrative,
            },
            "urgency": _urgency(rank, confidence),
        })

    true_we = db.query(WithdrawalEvent).filter(WithdrawalEvent.complaint_id == complaint_id).first()
    baseline_comparison = None
    if true_we is not None:
        ranked_baseline = candidates.sort_values("baseline_prob", ascending=False).reset_index(drop=True)
        ranked_advanced = candidates.reset_index(drop=True)
        b_rank = int(ranked_baseline.index[ranked_baseline["withdrawal_point_id"] == true_we.withdrawal_point_id][0]) + 1
        a_rank = int(ranked_advanced.index[ranked_advanced["withdrawal_point_id"] == true_we.withdrawal_point_id][0]) + 1
        baseline_comparison = {"baseline_rank_of_true_point": b_rank, "advanced_rank_of_true_point": a_rank}

    return {
        "complaint_id": complaint_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": registry.metadata["advanced_model_version"],
        "bank_name": complaint.bank_name,
        "predictions": predictions,
        "baseline_comparison": baseline_comparison,
        # How many cash-out points were actually scored for this complaint --
        # lets the UI show confidence relative to random chance (1/n_candidates)
        # instead of a bare percentage that reads as low in isolation.
        "n_candidates": int(len(candidates)),
    }
