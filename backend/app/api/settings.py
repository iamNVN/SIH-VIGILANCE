"""settings.py -- the Settings page's "Inject Live Cases" toggle. See
core/settings_state.py and core/activity_simulator.py for what it gates."""

from fastapi import APIRouter
from pydantic import BaseModel

from core import settings_state

router = APIRouter(prefix="/settings", tags=["settings"])


class InjectLiveCasesPayload(BaseModel):
    enabled: bool


@router.get("/inject-live-cases")
def get_inject_live_cases():
    return {"enabled": settings_state.get_inject_live_cases()}


@router.post("/inject-live-cases")
def set_inject_live_cases(payload: InjectLiveCasesPayload):
    settings_state.set_inject_live_cases(payload.enabled)
    return {"enabled": payload.enabled}
