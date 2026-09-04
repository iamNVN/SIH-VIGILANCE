"""events.py -- read endpoint for Command Center's "Live Investigation
Feed" panel. See core/event_log.py for what gets logged and why."""

from typing import Optional

from fastapi import APIRouter

from core import event_log

router = APIRouter(tags=["events"])


@router.get("/events")
def list_events(city: Optional[str] = None, limit: int = 20):
    return {"events": event_log.get_events(city=city, limit=limit)}
