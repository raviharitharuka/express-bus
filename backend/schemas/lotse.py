from typing import Any, Literal

from pydantic import Field

from schemas.common import CamelModel

Intent = Literal["launch_route", "idle_drivers", "breakdown", "station_buses", "driver_shortage", "unknown"]


class LotseRequest(CamelModel):
    question: str = Field(min_length=1, max_length=500)


class LotseResponse(CamelModel):
    question: str
    intent: Intent
    answer: str
    confidence: int
    data: dict[str, Any] | None
    suggested_questions: list[str]
