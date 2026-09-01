"""brief.py -- intervention brief endpoint, Blueprint Section 12 screen 6."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.graph import compute_related_complaints
from api.predict import predict
from brief.template_brief import generate_brief
from core.db import get_db

router = APIRouter(tags=["brief"])


@router.get("/brief/{complaint_id}")
def brief(complaint_id: int, db: Session = Depends(get_db)):
    prediction_response = predict(complaint_id, db=db)
    related = compute_related_complaints(complaint_id, as_of=None, db=db)
    text = generate_brief(prediction_response, related_complaints=related.get("related", []))
    return {"complaint_id": complaint_id, "brief_text": text}
