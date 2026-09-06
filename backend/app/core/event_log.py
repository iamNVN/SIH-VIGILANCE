"""
event_log.py -- an in-memory, real-time activity feed backing Command
Center's "Live Investigation Feed" panel.

Every entry here corresponds to something that ACTUALLY happened in this
running backend process at a real wall-clock moment -- never a fabricated
or synthetic timeline. Three event types are logged as real actions
happen: a complaint reveal (stream.py), a real /predict call (predict.py),
and an investigator decision (complaints.py's /decision). A fourth type
(one entry per detected fraud ring, using that ring's real size/complaint
count) is logged once at startup by rings.py, so the feed has real initial
content instead of starting empty -- not a periodic re-log, since the
underlying graph doesn't change during a session (see rings.py).

core/activity_simulator.py additionally emits events on a synthetic
cadence (there's no real continuous stream behind this static, historical
dataset) but every one is still built from real sampled data -- see that
module's docstring.

City-scoped like every other live-feed view in this app (see stats.py's
docstring): an investigator only sees events touching their own
jurisdiction; administrators (city=None) see everything.

DEDUPED AT THE SOURCE, NOT JUST IN THE UI
-------------------------------------------------------------------
Two independently real callers can legitimately fire for the same thing
close together -- e.g. an investigator opening a case's workspace (a real
/predict call) while activity_simulator.py's own story for that exact
complaint also happens to reach its "predict" step around the same time.
Both log calls are individually honest, but showing both is just visual
noise ("Case #0U00 -- Cash-out prediction generated" twice, verified
live). If the same (type, message) pair was already logged within
_DEDUPE_WINDOW_SECONDS, the repeat is silently dropped here rather than
appended -- one real event, not a manufactured pair of them.
"""

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional

_MAX_EVENTS = 200
_DEDUPE_WINDOW_SECONDS = 60
_DEDUPE_LOOKBACK = 20  # only the most recent handful -- old repeats are fine
_events = deque(maxlen=_MAX_EVENTS)
_lock = threading.Lock()
_next_id = [0]


def log_event(event_type: str, message: str, detail: str, city: Optional[str]):
    now = datetime.now(timezone.utc)
    with _lock:
        for e in list(_events)[:_DEDUPE_LOOKBACK]:
            if e["type"] == event_type and e["message"] == message:
                age = (now - datetime.fromisoformat(e["timestamp"])).total_seconds()
                if age < _DEDUPE_WINDOW_SECONDS:
                    return
                break  # deque is newest-first: the first match is the most recent
        _next_id[0] += 1
        _events.appendleft({
            "id": _next_id[0],
            "type": event_type,
            "message": message,
            "detail": detail,
            "city": city,
            "timestamp": now.isoformat(),
        })


def get_events(city: Optional[str] = None, limit: int = 20, event_type: Optional[str] = None) -> list[dict]:
    with _lock:
        items = list(_events)
    if city:
        items = [e for e in items if e["city"] == city]
    if event_type:
        items = [e for e in items if e["type"] == event_type]
    return items[: min(limit, _MAX_EVENTS)]
