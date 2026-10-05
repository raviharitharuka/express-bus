from datetime import date
from typing import Generic, Literal, TypeVar

from pydantic import ConfigDict, Field, field_validator, model_validator

from schemas.common import CamelModel

T = TypeVar("T")


class Counts(CamelModel):
    stations: int
    drivers: int
    buses: int
    routes: int
    trips: int


class AdminStatus(CamelModel):
    data_source: Literal["synthetic", "gtfs"]
    counts: Counts
    last_optimize_ms: int | None
    overrides_active: int


class DataSourceRequest(CamelModel):
    data_source: Literal["synthetic", "gtfs"]


class Page(CamelModel, Generic[T]):
    page: int
    page_size: int
    total: int
    items: list[T]


class DriverItem(CamelModel):
    driver_id: str
    home_station: str
    duty_id: str | None
    overtime_available: bool
    max_shift_hours: float
    vacation_dates: list[str]
    available: bool
    overridden: bool


class BusItem(CamelModel):
    bus_id: str
    station: str
    status: Literal["active", "spare", "maintenance", "broken"]
    type: str
    capacity: int
    overridden: bool


class StationItem(CamelModel):
    id: str
    name: str
    lat: float
    lng: float
    total_buses: int
    spare_buses: int
    drivers_based: int


class RouteItem(CamelModel):
    route_id: str
    name: str
    from_: str = Field(alias="from")
    to: str
    distance_km: float
    duration_min: int
    frequency_min: int


class _Patch(CamelModel):
    model_config = ConfigDict(extra="forbid")  # a typo like "availble" is an error, not a silent no-op

    @model_validator(mode="after")
    def not_empty(self):
        if not self.model_fields_set:
            raise ValueError("send at least one field to change")
        return self


class DriverPatch(_Patch):
    vacation_dates: list[str] | None = None
    overtime_available: bool | None = None
    max_shift_hours: float | None = Field(default=None, ge=4, le=13)
    available: bool | None = None

    @field_validator("vacation_dates")
    @classmethod
    def valid_dates(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for d in v:
                date.fromisoformat(d)  # raises ValueError -> 400
            v = sorted(set(v))
        return v


class BusPatch(_Patch):
    status: Literal["available", "maintenance", "broken"] | None = None
    station: str | None = None
