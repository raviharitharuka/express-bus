from fastapi import APIRouter

from schemas.lotse import LotseRequest, LotseResponse
from services.lotse import ask

router = APIRouter(tags=["lotse"])


# The URL stays /copilot (the assistant's old name) so existing clients keep working.
@router.post("/copilot", response_model=LotseResponse)
def lotse(req: LotseRequest):
    return ask(req)
