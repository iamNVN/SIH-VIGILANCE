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

THE CURSOR ACTUALLY GATES VISIBILITY, NOT JUST A COUNTER
----------------------------------------------------------
Originally this cursor advanced but nothing downstream checked it -- every
seeded complaint was visible everywhere from the moment the DB was seeded,
so "Simulate Complaint" changed nothing anyone could see (a real reported
bug). `core/replay_state.py`'s watermark is the fix: Command Center's
stats/feed/alerts/hotspots/timeseries all filter to
`Complaint.filed_at <= watermark`. The cursor starts at
`len(all complaints) - HOLDBACK` (not 0) so the dashboard opens already
populated with a realistic steady state, and the most recent HOLDBACK
complaints are what "Simulate Complaint" actually reveals one at a time.
Cases/search/direct case links are deliberately NOT gated (see
api/complaints.py) -- that's the full-archive investigator tool, not the
"live feed" view.
"""

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from core import replay_state
from core.db import SessionLocal, get_db

from .complaints import _to_out
from .feed import invalidate_feed_cache

router = APIRouter(tags=["stream"])


@router.get("/stream/status")
def stream_status(db: Session = Depends(get_db)):
    return replay_state.get_status(db)


@router.post("/stream/trigger-next")
def trigger_next(db: Session = Depends(get_db)):
    complaint = replay_state.advance(db)
    if complaint is None:
        return {"done": True, "complaint": None}
    invalidate_feed_cache()  # so the next dashboard fetch reflects this immediately, not after the 30s TTL
    # `_to_out`, not a bare ComplaintOut.model_validate(complaint): the raw
    # ORM object has no victim_name/victim_city attributes of its own (only
    # a `victim` relationship) -- model_validate left those None, showing
    # "Unknown victim · —" in the UI even for complaints with a real victim.
    return {"done": False, "complaint": _to_out(complaint).model_dump(mode="json")}


@router.post("/stream/reset")
def reset_stream(db: Session = Depends(get_db)):
    index = replay_state.reset(db)
    invalidate_feed_cache()
    return {"index": index}


@router.websocket("/stream/live-complaints")
async def live_complaints(websocket: WebSocket, interval_seconds: float = 3.0):
    await websocket.accept()
    db = SessionLocal()
    try:
        while True:
            complaint = replay_state.advance(db)
            if complaint is None:
                await websocket.send_json({"done": True})
                break
            invalidate_feed_cache()
            await websocket.send_json({
                "done": False,
                "complaint": _to_out(complaint).model_dump(mode="json"),
            })
            await asyncio.sleep(interval_seconds)
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
