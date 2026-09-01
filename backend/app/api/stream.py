"""
stream.py -- live-complaint replay mechanism (Blueprint Section 4/13/21).
Replays seeded historical complaints, oldest-first, over a WebSocket at an
accelerated pace, standing in for "a new complaint arrives live" -- every
downstream step (extraction/graph/prediction/explanation) still executes
for real on each replayed complaint (Section 14: "SIMULATED REPLAY of real
pipeline execution").

Kill-switch (Section 24): if the WebSocket proves flaky before demo day,
`POST /stream/trigger-next` advances the exact same cursor manually, one
complaint at a time, no code change needed to fall back.
"""

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import ComplaintOut
from core.db import SessionLocal, get_db
from models import Complaint

router = APIRouter(tags=["stream"])

_cursor = {"index": 0}


def _ordered_complaint_ids(db: Session) -> list[int]:
    rows = db.execute(select(Complaint.id).order_by(Complaint.filed_at.asc())).scalars().all()
    return list(rows)


@router.post("/stream/trigger-next")
def trigger_next(db: Session = Depends(get_db)):
    ids = _ordered_complaint_ids(db)
    if not ids:
        return {"done": True, "complaint": None}
    if _cursor["index"] >= len(ids):
        return {"done": True, "complaint": None}
    complaint = db.get(Complaint, ids[_cursor["index"]])
    _cursor["index"] += 1
    return {"done": False, "complaint": ComplaintOut.model_validate(complaint).model_dump(mode="json")}


@router.post("/stream/reset")
def reset_stream():
    _cursor["index"] = 0
    return {"index": 0}


@router.websocket("/stream/live-complaints")
async def live_complaints(websocket: WebSocket, interval_seconds: float = 3.0):
    await websocket.accept()
    db = SessionLocal()
    try:
        ids = _ordered_complaint_ids(db)
        while True:
            if _cursor["index"] >= len(ids):
                await websocket.send_json({"done": True})
                break
            complaint = db.get(Complaint, ids[_cursor["index"]])
            _cursor["index"] += 1
            await websocket.send_json({
                "done": False,
                "complaint": ComplaintOut.model_validate(complaint).model_dump(mode="json"),
            })
            await asyncio.sleep(interval_seconds)
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
