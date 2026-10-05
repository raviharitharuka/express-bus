from fastapi import APIRouter

from schemas.emergency import EmergencyRequest, EmergencyResponse
from services import data
from services.emergency import handle_incident

router = APIRouter(tags=["emergency"])


@router.post("/emergency", response_model=EmergencyResponse)
def emergency(req: EmergencyRequest):
    return handle_incident(req)


@router.post("/emergency/reset")
def reset():
    """Undo all breakdowns and dispatches made since the server started (demo helper)."""
    data.reset_live_state()
    return {"status": "reset"}
