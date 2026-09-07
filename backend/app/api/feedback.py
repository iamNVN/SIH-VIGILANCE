"""feedback.py -- read side of the active-learning feedback loop (Blueprint
Section 15/23). complaints.py's apply_decision() is the write side: every
real Approve/Reject snapshots the top prediction being acted on and labels
it (correct_bool = approved). This endpoint just reports how many real
labels have accumulated so far.

Automated retraining IS wired to this table now (core/retrain_manager.py --
triggered by apply_decision() once RETRAIN_LABEL_THRESHOLD new labels
accumulate). Honest scope boundary that still holds: retraining fits
against the generator's own ground-truth withdrawal_events, same as
always -- these labels are the real, honest TRIGGER (proof of genuine
ongoing usage), not a training target that reshapes what the model
predicts. See retrain_manager.py's docstring for why that boundary is
correct for a synthetic-ground-truth demo, not a limitation to hide.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core import retrain_manager
from core.db import get_db
from models import InvestigatorFeedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/summary")
def feedback_summary(db: Session = Depends(get_db)):
    total = db.execute(select(func.count(InvestigatorFeedback.id))).scalar_one()
    agree = db.execute(
        select(func.count(InvestigatorFeedback.id)).where(InvestigatorFeedback.correct_bool.is_(True))
    ).scalar_one()
    return {"total_labels": total, "agree": agree, "disagree": total - agree}


@router.get("/retrain/status")
def get_retrain_status():
    return retrain_manager.status()


@router.post("/retrain/trigger")
def post_retrain_trigger():
    started = retrain_manager.trigger_now()
    if not started:
        raise HTTPException(409, "A retrain is already in progress.")
    return {"started": True}
