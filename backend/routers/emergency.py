from fastapi import APIRouter

from schemas.emergency import EmergencyRequest, EmergencyResponse
from services.emergency import handle_incident

router = APIRouter(tags=["emergency"])


@router.post("/emergency", response_model=EmergencyResponse)
def emergency(req: EmergencyRequest):
    return handle_incident(req)
