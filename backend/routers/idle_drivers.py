from fastapi import APIRouter

from schemas.idle import IdleDriversResponse
from services.idle import get_idle_drivers

router = APIRouter(tags=["drivers"])


@router.get("/idle-drivers", response_model=IdleDriversResponse)
def idle_drivers(date: str | None = None):
    return get_idle_drivers(date)
