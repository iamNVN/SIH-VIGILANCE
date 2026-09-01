"""explain.py -- SHAP explanation endpoint, Blueprint Section 12 screen 8
"Model Explanation". Defaults to explaining the #1 ranked candidate; pass
`withdrawal_point_id` to explain any other candidate for the same complaint."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core import dataset_provider
from core.db import get_db
from core.model_registry import registry
from graph_engine.features import ADVANCED_FEATURE_COLUMNS, build_candidate_features
from ml import explain as shap_explain
from models import Complaint

router = APIRouter(tags=["explain"])


@router.get("/explain/{complaint_id}")
def explain(complaint_id: int, withdrawal_point_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    if not registry.ready:
        raise HTTPException(503, "models not trained yet -- run `python -m ml.train` first")

    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(404, f"complaint {complaint_id} not found")

    ds = dataset_provider.get_dataset()
    import pandas as pd

    complaint_row = pd.Series({
        "id": complaint.id, "victim_id": complaint.victim_id,
        "filed_at": pd.Timestamp(complaint.filed_at),
        "amount_lost": complaint.amount_lost, "bank_name": complaint.bank_name,
    })
    candidates = build_candidate_features(ds, complaint_row)
    candidates["advanced_prob"] = registry.advanced_calibrated.predict_proba(candidates[ADVANCED_FEATURE_COLUMNS])[:, 1]
    candidates = candidates.sort_values("advanced_prob", ascending=False).reset_index(drop=True)

    if withdrawal_point_id is not None:
        match = candidates[candidates["withdrawal_point_id"] == withdrawal_point_id]
        if match.empty:
            raise HTTPException(404, f"withdrawal point {withdrawal_point_id} is not a candidate for this complaint")
        row = match.iloc[0]
    else:
        row = candidates.iloc[0]

    explanation = shap_explain.explain_row(registry.advanced_raw, ADVANCED_FEATURE_COLUMNS, row)
    return {
        "complaint_id": complaint_id,
        "withdrawal_point_id": int(row["withdrawal_point_id"]),
        "confidence": round(float(row["advanced_prob"]), 4),
        "shap_values": explanation["shap_values"],
        "top_features": explanation["top_features"],
    }
