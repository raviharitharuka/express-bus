import time

from fastapi import APIRouter

from schemas.optimize import OptimizeRequest, OptimizeResponse
from services import admin
from services.optimizer import optimize as run_optimize

router = APIRouter(tags=["optimization"])


@router.post("/optimize", response_model=OptimizeResponse)
def optimize(req: OptimizeRequest | None = None):
    start = time.perf_counter()
    result = run_optimize(req or OptimizeRequest())
    admin.record_optimize_ms(round((time.perf_counter() - start) * 1000))  # shown by GET /admin/status
    return result
