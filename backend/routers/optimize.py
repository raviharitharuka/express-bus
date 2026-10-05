from fastapi import APIRouter

from schemas.optimize import OptimizeRequest, OptimizeResponse
from services.optimizer import optimize as run_optimize

router = APIRouter(tags=["optimization"])


@router.post("/optimize", response_model=OptimizeResponse)
def optimize(req: OptimizeRequest | None = None):
    return run_optimize(req or OptimizeRequest())
