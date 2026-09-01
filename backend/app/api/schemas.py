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


class ComplaintOut(BaseModel):
    id: int
    victim_id: int
    filed_at: datetime
    amount_lost: float
    narrative_text: str
    bank_name: str
    status: str

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    prediction_id: int
    correct_bool: bool
    investigator_note: Optional[str] = None
