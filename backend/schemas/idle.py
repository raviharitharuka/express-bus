from schemas.common import CamelModel


class IdleWindow(CamelModel):
    start: str
    end: str
    station: str


class IdleDriver(CamelModel):
    driver_id: str
    home_station: str
    duty_start: str
    duty_end: str
    driving_hours: float
    idle_hours: float
    free_capacity_hours: float
    idle_windows: list[IdleWindow]
    recommended_route: str | None


class IdleDriversResponse(CamelModel):
    date: str
    total_drivers: int
    working_drivers: int
    idle_driver_count: int
    total_idle_hours: float
    total_free_capacity_hours: float
    drivers: list[IdleDriver]
