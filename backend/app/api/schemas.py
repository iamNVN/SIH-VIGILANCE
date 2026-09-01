"""schemas.py -- Pydantic request/response models for the API layer."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ComplaintCreate(BaseModel):
    victim_id: int
    amount_lost: float
    narrative_text: str
    bank_name: str
    filed_at: Optional[datetime] = None


class ExtractedEntities(BaseModel):
    """Lightweight regex extraction over narrative_text (Blueprint Section 4:
    "Regex + spaCy rule-based Matcher... NOT a trained transformer"). Only
    the regex half is implemented today -- good enough for the generator's
    templated narratives and the Complaint Detail demo beat (Section 13)."""

    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    amount: Optional[float] = None


class ComplaintOut(BaseModel):
    id: int
    victim_id: int
    victim_name: Optional[str] = None
    victim_city: Optional[str] = None
    filed_at: datetime
    amount_lost: float
    narrative_text: str
    bank_name: str
    status: str
    extracted_entities: Optional[ExtractedEntities] = None

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    prediction_id: int
    correct_bool: bool
    investigator_note: Optional[str] = None
