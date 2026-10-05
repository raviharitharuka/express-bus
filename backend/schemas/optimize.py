from typing import Literal

from pydantic import Field, field_validator, model_validator

from schemas.common import CamelModel
from services.time_utils import to_hhmm, to_min


class ExpressCandidate(CamelModel):
    route_id: str | None = None
    name: str | None = None
    start_station: str
    end_station: str
    headway_min: int = Field(ge=10, le=240)
    service_start: str
    service_end: str
    trip_duration_min: int = Field(ge=5, le=120)
    turnaround_min: int = Field(default=10, ge=0, le=60)

    @field_validator("service_start", "service_end")
    @classmethod
    def valid_time(cls, v: str) -> str:
        return to_hhmm(to_min(v))  # validates and zero-pads "9:00" -> "09:00"

    @model_validator(mode="after")
    def check(self):
        if self.start_station == self.end_station:
            raise ValueError("startStation and endStation must differ")
        if self.service_start >= self.service_end:
            raise ValueError("serviceStart must be before serviceEnd")
        return self


class OptimizeRequest(CamelModel):
    date: str | None = None
    allow_overtime: bool = True
    candidates: list[ExpressCandidate] | None = Field(default=None, min_length=1, max_length=5)


class TripAssignment(CamelModel):
    trip_id: str
    departure: str
    returns_at: str
    driver: str | None
    kind: Literal["idle", "overtime", "new-driver", "uncovered"]


class RouteResult(CamelModel):
    route: str
    name: str
    start_station: str
    end_station: str
    trips_requested: int
    trips_covered: int
    feasible: bool
    new_drivers_required: int
    idle_hours_used: float
    overtime_hours_used: float
    utilization_before: float
    utilization_after: float
    reason: str
    assignments: list[TripAssignment]


class OptimizeResponse(CamelModel):
    date: str
    allow_overtime: bool
    current_utilization: float
    optimized_utilization: float
    total_idle_hours_available: float
    total_idle_hours_used: float
    overtime_hours_used: float
    new_drivers_required: int
    recommended: list[str]
    summary: str
    recommendations: list[RouteResult]
