from typing import Literal

from pydantic import AliasChoices, Field

from schemas.common import CamelModel


class EmergencyRequest(CamelModel):
    incident_type: Literal["BREAKDOWN", "DRIVER_SICK", "ROAD_CLOSURE"]
    # "location" is accepted too (the incident format in project_context.md)
    station: str = Field(validation_alias=AliasChoices("station", "location"))
    bus_id: str | None = None
    driver_id: str | None = None
    time: str | None = None


class TimelineStep(CamelModel):
    time: str
    step: str


class EmergencyResponse(CamelModel):
    incident_id: str
    incident_type: str
    status: Literal["DISPATCHED", "NO_BUS_AVAILABLE", "NO_DRIVER_AVAILABLE"]
    broken_bus: str | None
    replacement_bus: str | None
    driver: str | None
    source_station: str | None
    destination_station: str
    distance_km: float | None
    eta_minutes: int | None
    timeline: list[TimelineStep]
