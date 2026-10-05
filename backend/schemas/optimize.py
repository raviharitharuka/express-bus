from pydantic import Field

from schemas.common import CamelModel


class OptimizeRequest(CamelModel):
    date: str | None = None
    allow_overtime: bool = False
    max_new_routes: int = Field(default=5, ge=1, le=10)


class RouteRecommendation(CamelModel):
    route: str
    name: str
    idle_hours_used: float
    new_drivers_required: int
    feasible: bool
    assigned_drivers: list[str]
    reason: str


class OptimizeResponse(CamelModel):
    date: str
    current_utilization: float
    optimized_utilization: float
    total_idle_hours_available: float
    total_idle_hours_used: float
    new_drivers_required: int
    recommendations: list[RouteRecommendation]
