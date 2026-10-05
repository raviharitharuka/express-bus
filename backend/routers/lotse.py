from fastapi import APIRouter

from schemas.lotse import LotseRequest, LotseResponse
from services.lotse import ask

router = APIRouter(tags=["lotse"])


@router.post("/lotse", response_model=LotseResponse)
def lotse(req: LotseRequest):
    return ask(req)


# Old name, kept so existing clients (and the frontend) keep working.
@router.post("/copilot", response_model=LotseResponse, summary="Lotse (alias of POST /lotse)")
def copilot(req: LotseRequest):
    return lotse(req)
