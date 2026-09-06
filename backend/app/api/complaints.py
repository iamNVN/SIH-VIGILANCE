"""complaints.py -- intake + list endpoints (Blueprint Section 4/21)."""

from datetime import datetime, timezone

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from api.schemas import ComplaintCreate, ComplaintOut, DecisionCreate, DecisionOut
from core import dataset_provider
from core.db import get_db
from models import Complaint, Victim
from nlp.entity_extraction import extract_entities

router = APIRouter(prefix="/complaints", tags=["complaints"])

_URGENCY_RANK = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}


def _risk_lookup() -> dict:
    """complaint_id -> (urgency_rank, confidence), from the same cached
    batch feed the Predictions/Alerts pages use (see api/feed.py) -- no
    separate computation, so "sort by risk" here always agrees with what
    those pages show for the same complaint. A complaint this feed hasn't
    scored (closed, or the batch's model isn't ready yet) sorts last, not
    excluded -- Cases is the full-archive browse view, unlike Alerts/
    Predictions which only ever show scored open complaints."""
    from .feed import cached_feed_if_warm

    items = cached_feed_if_warm() or []
    return {
        it["complaint_id"]: (_URGENCY_RANK.get(it["top_prediction"]["urgency"], 0), it["top_prediction"]["confidence"])
        for it in items
    }


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


def _filtered(stmt, q: Optional[str], city: Optional[str], status: Optional[str] = None, revealed: Optional[bool] = None):
    """`city` is a hard AND filter (an investigator's jurisdiction scope --
    see stats.py's docstring); `q` is a free-text OR search within that
    scope; `status` is a hard AND filter on the complaint's real `status`
    column (e.g. "open" for Command Center's "Pending Action" card --
    same value that gate already writes/reads, not a separate concept).
    `revealed`, when given, matches Cases up with a live-feed count that's
    itself gated to `revealed` (see stats.py's open_complaints) -- without
    it, "Pending Action" (a revealed-only count) linking to `status=open`
    here would show every open complaint ever, revealed or not, a
    real reported mismatch (~21 on the card vs 110 on the list). Cases'
    own default (unscoped) browsing is unaffected -- this only applies
    when a caller explicitly asks for it. Both q/city join Victim, so the
    join happens once regardless of which filters are active."""
    if q or city:
        stmt = stmt.join(Victim)
    if city:
        stmt = stmt.where(Victim.city == city)
    if status:
        stmt = stmt.where(Complaint.status == status)
    if revealed is not None:
        stmt = stmt.where(Complaint.revealed.is_(revealed))
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Victim.name_fake.ilike(needle),
                Victim.city.ilike(needle),
                Complaint.bank_name.ilike(needle),
                Complaint.id == (int(q) if q.strip().isdigit() else -1),
            )
        )
    return stmt


@router.get("", response_model=list[ComplaintOut])
def list_complaints(
    skip: int = 0,
    limit: int = 50,
    q: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    revealed: Optional[bool] = None,
    sort: str = "newest",
    db: Session = Depends(get_db),
):
    limit = min(limit, 200)
    stmt = _filtered(select(Complaint).options(joinedload(Complaint.victim)), q, city, status, revealed)

    if sort in ("risk", "confidence"):
        # Can't express "order by this complaint's model confidence" in SQL
        # (confidence lives in feed.py's cache, not a DB column) -- fetch the
        # filtered set unsorted, rank in Python against that cache, then
        # paginate. Fine at this dataset's size (low hundreds of rows);
        # would need a real query-side rethink at a much bigger scale.
        risk = _risk_lookup()
        rows = db.execute(stmt).scalars().all()
        rows.sort(key=lambda r: risk.get(r.id, (0, 0.0)), reverse=True)
        rows = rows[skip: skip + limit]
    else:
        order = Complaint.filed_at.asc() if sort == "oldest" else Complaint.filed_at.desc()
        rows = db.execute(stmt.order_by(order).offset(skip).limit(limit)).scalars().all()

    return [_to_out(r) for r in rows]


@router.get("/count")
def count_complaints(
    q: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    revealed: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    stmt = _filtered(select(Complaint), q, city, status, revealed)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    return {"total": total}


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(complaint_id: int, db: Session = Depends(get_db)):
    row = db.get(Complaint, complaint_id)
    if row is None:
        raise HTTPException(404, f"complaint {complaint_id} not found")
    return _to_out(row)


# The Intervention Brief's "Requires sign-off · not auto-executed" label is
# the honest boundary here: this records a real, persisted investigator
# decision (survives a refresh, changes the case's status everywhere it's
# shown -- Cases, Command Center's tables, /stats' open_complaints and
# amount-at-risk, which a decided case correctly drops out of, same as
# feed.py's Predictions/Alerts batch) -- but it does NOT call a bank, freeze
# an account, or take any real external action. `next_step` says what a
# real system would do next, clearly labeled as simulated, rather than
# either silently doing nothing (the old cosmetic-only version) or
# pretending an integration exists that doesn't.
_NEXT_STEP = {
    "approved": (
        "Flagged for {bank}'s fraud response team -- a freeze request against the "
        "predicted cash-out account would be logged next. (Simulated: no real bank "
        "integration exists in this demo.)"
    ),
    "rejected": (
        "Dismissed from the active response queue. No further automated action will "
        "be taken on this case. (Simulated: no real bank integration exists in this demo.)"
    ),
}


def apply_decision(db: Session, complaint: Complaint, decision: str) -> DecisionOut:
    """Core decision-recording logic -- shared by the real investigator-
    facing endpoint below and core/demo_seed.py's startup seeding, so a
    seeded decision is recorded exactly the same way a real one is (status
    change, feed removal, event log entry) and is indistinguishable from a
    real one anywhere else in the app (Cases, Command Center, /stats,
    Audit Trail). One place to update beats two copies drifting apart."""
    was_open = complaint.status == "open"
    complaint.status = f"action_{decision}"
    db.commit()

    if was_open:
        # This complaint no longer belongs in the "open" batch feed
        # (Predictions/Alerts, and /stats' high_risk_cases) -- without this
        # it would keep showing there as HIGH/scored until the next full
        # rebuild, contradicting the status change just made.
        from .feed import remove_complaint_from_feed

        remove_complaint_from_feed(complaint.id)

    from core import event_log
    from core.case_code import case_code

    from .feed import cached_feed_if_warm

    # Same detail line the simulated version of this event shows (see
    # activity_simulator.py) -- the real predicted location for this case
    # if it's in the cached batch, else its bank, never a placeholder.
    items = cached_feed_if_warm() or []
    match = next((it for it in items if it["complaint_id"] == complaint.id), None)
    detail = match["top_prediction"]["name"] if match else complaint.bank_name

    verb = "approved for action" if decision == "approved" else "rejected"
    event_log.log_event(
        "decision",
        f"Case #{case_code(complaint.id)} — {verb}",
        detail,
        complaint.victim.city if complaint.victim else None,
    )

    return DecisionOut(status=complaint.status, next_step=_NEXT_STEP[decision].format(bank=complaint.bank_name))


@router.post("/{complaint_id}/decision", response_model=DecisionOut)
def decide_complaint(complaint_id: int, payload: DecisionCreate, db: Session = Depends(get_db)):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(422, "decision must be 'approved' or 'rejected'")

    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(404, f"complaint {complaint_id} not found")

    return apply_decision(db, complaint, payload.decision)


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
