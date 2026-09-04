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

from collections import defaultdict
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core import dataset_provider, event_log
from core.case_code import case_code
from core.db import get_db
from core.model_registry import registry
from graph_engine.features import ADVANCED_FEATURE_COLUMNS, BASELINE_FEATURE_COLUMNS, build_candidate_features
from ml import explain as shap_explain
from models import Complaint, WithdrawalEvent

router = APIRouter(tags=["predict"])

TOP_K = 5

# A real, honestly-labeled usage counter -- not a fabricated "Predictions
# Today" number. In-memory, keyed by real (not the dataset's fictional
# June-Aug 2026) UTC calendar date, so it resets whenever the backend
# restarts and never claims history it doesn't have. The complaints being
# scored carry fictional filed_at dates, but the act of *querying* a
# prediction happens at real wall-clock time, which is what this counts.
_predictions_served_by_date: dict[str, int] = defaultdict(int)


def record_prediction_served():
    today = datetime.now(timezone.utc).date().isoformat()
    _predictions_served_by_date[today] += 1


def predictions_served_today() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    return _predictions_served_by_date.get(today, 0)


def _complaint_row(complaint: Complaint) -> pd.Series:
    return pd.Series({
        "id": complaint.id,
        "victim_id": complaint.victim_id,
        "filed_at": pd.Timestamp(complaint.filed_at),
        "amount_lost": complaint.amount_lost,
        "bank_name": complaint.bank_name,
    })


def lift_urgency(confidence: float, n_candidates: int) -> str:
    # Absolute-confidence thresholds (e.g. "HIGH if >= 0.5") don't work here:
    # with ~40 candidates per city and a calibrated model, top-pick confidence
    # rarely exceeds ~20-25% even for the model's best, most confident calls
    # (see Analytics -- Precision@1 is real and modest) -- an 0.5 bar meant
    # every complaint landed on "MEDIUM" forever, regardless of how much
    # better than chance the top pick actually was. Lift over random chance
    # among THIS complaint's own candidates is the comparable signal across
    # cities/complaints with different candidate-set sizes. Shared with
    # feed.py so the single-case view and the cross-case feed agree.
    if n_candidates <= 0:
        return "LOW"
    lift = confidence / (1 / n_candidates)
    if lift >= 5:
        return "HIGH"
    if lift >= 2:
        return "MEDIUM"
    return "LOW"


@router.post("/predict/{complaint_id}")
def predict(complaint_id: int, db: Session = Depends(get_db)):
    if not registry.ready:
        raise HTTPException(503, "models not trained yet -- run `python -m ml.train` first")

    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(404, f"complaint {complaint_id} not found")

    record_prediction_served()
    ds = dataset_provider.get_dataset()
    complaint_row = _complaint_row(complaint)
    candidates = build_candidate_features(ds, complaint_row)

    candidates["baseline_prob"] = registry.baseline_calibrated.predict_proba(candidates[BASELINE_FEATURE_COLUMNS])[:, 1]
    candidates["advanced_prob"] = registry.advanced_calibrated.predict_proba(candidates[ADVANCED_FEATURE_COLUMNS])[:, 1]
    candidates = candidates.sort_values("advanced_prob", ascending=False).reset_index(drop=True)

    n_candidates = len(candidates)
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
            "urgency": lift_urgency(confidence, n_candidates),
        })

    if predictions:
        top = predictions[0]
        event_log.log_event(
            "prediction_generated",
            f"Case #{case_code(complaint_id)} — Cash-out prediction generated",
            f"{top['name']} · {round(top['confidence'] * 100, 1)}%",
            complaint.victim.city if complaint.victim else None,
        )

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
        "n_candidates": int(n_candidates),
    }
