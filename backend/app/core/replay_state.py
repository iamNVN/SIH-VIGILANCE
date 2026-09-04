"""
replay_state.py -- the live-replay cursor and watermark, shared by
api/stream.py (owns advancing/resetting it) and api/feed.py (reads it to
gate what Command Center's dashboard shows). Split into its own module
so neither of those two needs to import the other -- feed.py needs the
watermark, stream.py needs to invalidate feed.py's cache after advancing
the cursor, and putting the cursor itself in either of those two would
make that a circular import.

See api/stream.py's module docstring for the full "why" -- short version:
the cursor didn't used to gate anything, so "Simulate Complaint" changed
nothing anyone could see. Everything with filed_at <= the watermark is
"arrived"; HOLDBACK-many of the most recent complaints start un-arrived so
there's something for Simulate to actually reveal.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Complaint

HOLDBACK = 20
BEFORE_ANYTHING = datetime(1970, 1, 1)

_cursor = {"index": None}


def _ordered_complaint_ids(db: Session) -> list[int]:
    rows = db.execute(select(Complaint.id).order_by(Complaint.filed_at.asc())).scalars().all()
    return list(rows)


def _ensure_initialized(ids: list[int]):
    if _cursor["index"] is None:
        _cursor["index"] = max(0, len(ids) - HOLDBACK)


def get_status(db: Session) -> dict:
    ids = _ordered_complaint_ids(db)
    _ensure_initialized(ids)
    return {"revealed": _cursor["index"], "total": len(ids), "done": _cursor["index"] >= len(ids)}


def get_live_watermark(db: Session) -> datetime:
    """The filed_at of the most recent 'arrived' complaint. Everything with
    filed_at <= this is visible on Command Center; nothing later is, until
    `/stream/trigger-next` reveals it."""
    ids = _ordered_complaint_ids(db)
    _ensure_initialized(ids)
    if not ids or _cursor["index"] <= 0:
        return BEFORE_ANYTHING
    last_revealed_id = ids[min(_cursor["index"], len(ids)) - 1]
    complaint = db.get(Complaint, last_revealed_id)
    return complaint.filed_at if complaint else BEFORE_ANYTHING


def advance(db: Session):
    """Reveals the next complaint. Returns it (or None if already caught up)."""
    ids = _ordered_complaint_ids(db)
    _ensure_initialized(ids)
    if not ids or _cursor["index"] >= len(ids):
        return None
    complaint = db.get(Complaint, ids[_cursor["index"]])
    _cursor["index"] += 1
    return complaint


def reset(db: Session):
    ids = _ordered_complaint_ids(db)
    _cursor["index"] = max(0, len(ids) - HOLDBACK)
    return _cursor["index"]
