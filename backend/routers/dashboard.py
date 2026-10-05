from fastapi import APIRouter

from schemas.dashboard import DashboardResponse
from services.dashboard import get_dashboard

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(date: str | None = None):
    return get_dashboard(date)
