"""
settings_state.py -- process-wide runtime toggles, changed from the
Settings page.

In-memory only (resets on backend restart, same as everything else in
this demo that isn't in the DB) -- a single flag shared by every viewer,
not per-user, since the thing it gates (core/activity_simulator.py's real
complaint injection) is itself one background thread shared by the whole
backend process, not something scoped to one investigator's session.
"""

import threading

_lock = threading.Lock()
_state = {"inject_live_cases": True}


def get_inject_live_cases() -> bool:
    with _lock:
        return _state["inject_live_cases"]


def set_inject_live_cases(enabled: bool):
    with _lock:
        _state["inject_live_cases"] = enabled
