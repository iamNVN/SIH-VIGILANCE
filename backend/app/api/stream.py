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

THE REVEAL FLAG ACTUALLY GATES VISIBILITY, NOT JUST A COUNTER
----------------------------------------------------------------
Originally an in-memory cursor advanced but nothing downstream checked it --
every seeded complaint was visible everywhere from the moment the DB was
seeded, so "Simulate Complaint" changed nothing anyone could see (a real
reported bug). `core/replay_state.py`'s `Complaint.revealed` column is the
fix: Command Center's stats/feed/alerts/hotspots/timeseries all filter to
`revealed = true`. seed_db.py holds back the most recent complaints IN
EACH CITY (not one global holdback), and `city` here lets an
investigator's Simulate Complaint reveal the next one in THEIR OWN
jurisdiction specifically -- otherwise it could reveal some other city's
complaint, which their (city-scoped) dashboard would just filter right
back out, making the button look broken again. Cases/search/direct case
links are deliberately NOT gated (see api/complaints.py) -- that's the
full-archive investigator tool, not the "live feed" view.
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from core import replay_state
from core.db import SessionLocal, get_db

from .complaints import _to_out
from .feed import add_revealed_complaint_to_feed, rebuild_feed_in_background

router = APIRouter(tags=["stream"])


@router.get("/stream/status")
def stream_status(city: Optional[str] = None, db: Session = Depends(get_db)):
    return replay_state.get_status(db, city=city)


@router.post("/stream/trigger-next")
def trigger_next(city: Optional[str] = None, db: Session = Depends(get_db)):
    complaint = replay_state.advance(db, city=city)
    if complaint is None:
        return {"done": True, "complaint": None}
    # Scores just this one complaint and inserts it into the already-built
    # feed cache -- see feed.py's docstring for why this replaced a full
    # cache invalidation (which forced whoever's request landed next to pay
    # a ~25-30s recompute of the entire batch just for one new arrival).
    add_revealed_complaint_to_feed(complaint)
    # `_to_out`, not a bare ComplaintOut.model_validate(complaint): the raw
    # ORM object has no victim_name/victim_city attributes of its own (only
    # a `victim` relationship) -- model_validate left those None, showing
    # "Unknown victim · —" in the UI even for complaints with a real victim.
    return {"done": False, "complaint": _to_out(complaint).model_dump(mode="json")}


@router.post("/stream/reset")
def reset_stream(db: Session = Depends(get_db)):
    holdback_count = replay_state.reset(db)
    # Unlike a single reveal, reset changes which complaints belong in the
    # feed at all (a bulk un-reveal), so it's the one case that still needs
    # a full recompute -- done in the background so this endpoint's own
    # response doesn't block on it.
    rebuild_feed_in_background()
    return {"held_back": holdback_count}


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
            add_revealed_complaint_to_feed(complaint)
            await websocket.send_json({
                "done": False,
                "complaint": _to_out(complaint).model_dump(mode="json"),
            })
            await asyncio.sleep(interval_seconds)
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
