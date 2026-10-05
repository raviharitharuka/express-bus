from typing import Literal

from schemas.common import CamelModel


class Kpis(CamelModel):
    driver_utilization: float
    fleet_utilization: float
    available_drivers: int
    available_buses: int
    predicted_shortages: int
    additional_routes_identified: int


class StationStatus(CamelModel):
    name: str
    total_buses: int
    available_buses: int
    maintenance_buses: int
    drivers_on_duty: int


class Recommendation(CamelModel):
    title: str
    reason: str
    confidence: int


class Alert(CamelModel):
    level: Literal["info", "warning", "critical"]
    message: str


class DashboardResponse(CamelModel):
    date: str
    kpis: Kpis
    stations: list[StationStatus]
    recommendation: Recommendation
    alerts: list[Alert]
