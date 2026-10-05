from fastapi import APIRouter

from schemas.copilot import CopilotRequest, CopilotResponse
from services.copilot import ask

router = APIRouter(tags=["copilot"])


@router.post("/copilot", response_model=CopilotResponse)
def copilot(req: CopilotRequest):
    return ask(req)
