"""complaints.py -- intake + list endpoints (Blueprint Section 4/21)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import ComplaintCreate, ComplaintOut
from core import dataset_provider
from core.db import get_db
from models import Complaint, Victim

router = APIRouter(prefix="/complaints", tags=["complaints"])


@router.get("", response_model=list[ComplaintOut])
def list_complaints(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    limit = min(limit, 200)
    rows = db.execute(
        select(Complaint).order_by(Complaint.filed_at.desc()).offset(skip).limit(limit)
    ).scalars().all()
    return rows


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(complaint_id: int, db: Session = Depends(get_db)):
    row = db.get(Complaint, complaint_id)
    if row is None:
        raise HTTPException(404, f"complaint {complaint_id} not found")
    return row


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
    return complaint
