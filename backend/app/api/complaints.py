"""complaints.py -- intake + list endpoints (Blueprint Section 4/21)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from api.schemas import ComplaintCreate, ComplaintOut
from core import dataset_provider
from core.db import get_db
from models import Complaint, Victim
from nlp.entity_extraction import extract_entities

router = APIRouter(prefix="/complaints", tags=["complaints"])


def _to_out(complaint: Complaint) -> ComplaintOut:
    return ComplaintOut(
        id=complaint.id,
        victim_id=complaint.victim_id,
        victim_name=complaint.victim.name_fake if complaint.victim else None,
        victim_city=complaint.victim.city if complaint.victim else None,
        filed_at=complaint.filed_at,
        amount_lost=complaint.amount_lost,
        narrative_text=complaint.narrative_text,
        bank_name=complaint.bank_name,
        status=complaint.status,
        extracted_entities=extract_entities(complaint.narrative_text),
    )


@router.get("", response_model=list[ComplaintOut])
def list_complaints(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    limit = min(limit, 200)
    rows = db.execute(
        select(Complaint).options(joinedload(Complaint.victim))
        .order_by(Complaint.filed_at.desc()).offset(skip).limit(limit)
    ).scalars().all()
    return [_to_out(r) for r in rows]


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(complaint_id: int, db: Session = Depends(get_db)):
    row = db.get(Complaint, complaint_id)
    if row is None:
        raise HTTPException(404, f"complaint {complaint_id} not found")
    return _to_out(row)


@router.post("", response_model=ComplaintOut, status_code=201)
def create_complaint(payload: ComplaintCreate, db: Session = Depends(get_db)):
    victim = db.get(Victim, payload.victim_id)
    if victim is None:
        raise HTTPException(404, f"victim {payload.victim_id} not found")

    complaint = Complaint(
        victim_id=payload.victim_id,
        amount_lost=payload.amount_lost,
        narrative_text=payload.narrative_text,
        bank_name=payload.bank_name,
        filed_at=payload.filed_at or datetime.now(timezone.utc),
        status="open",
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    dataset_provider.refresh()
    return _to_out(complaint)
