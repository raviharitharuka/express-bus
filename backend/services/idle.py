"""Driver idle-time detection: gaps between trips long enough to run extra service."""

from dataclasses import dataclass

from schemas.idle import IdleDriver, IdleDriversResponse, IdleWindow
from services import data
from services.time_utils import hours, to_hhmm, to_min, tomorrow

MIN_IDLE_MIN = 60  # shortest gap worth reporting (fits one express round trip)


@dataclass
class Window:
    driver_id: str
    station: str
    start: int  # minutes since midnight
    end: int
    kind: str = "idle"  # idle | overtime

    @property
    def minutes(self) -> int:
        return self.end - self.start

    def fits(self, start: int, end: int) -> bool:
        return self.start <= start and end <= self.end


def idle_windows(day: data.Day) -> list[Window]:
    """Split-shift breaks and long layovers, wherever the driver is standing."""
    trips = data.trips_by_duty()
    out = []
    for duty in day.working_duties():
        legs = trips[duty["dutyId"]]
        for prev, nxt in zip(legs, legs[1:]):
            gap_start, gap_end = to_min(prev["arrivalTime"]), to_min(nxt["departureTime"])
            if gap_end - gap_start >= MIN_IDLE_MIN:
                out.append(Window(duty["driverId"], prev["endStation"], gap_start, gap_end))
    return out


def overtime_windows(day: data.Day) -> list[Window]:
    """Time after the duty ends, up to maxShiftHours, for drivers who accept overtime.

    The driver is where their last trip ended. That's the home station in the synthetic data, but
    real duties (cut from a bus's day) often end elsewhere."""
    drivers = data.drivers()
    trips = data.trips_by_duty()
    out = []
    for duty in day.working_duties():
        drv = drivers[duty["driverId"]]
        start = to_min(duty["start"])
        end, limit = to_min(duty["end"]), start + round(drv["maxShiftHours"] * 60)
        if drv["overtimeAvailable"] and limit - end >= MIN_IDLE_MIN:
            out.append(Window(drv["driverId"], trips[duty["dutyId"]][-1]["endStation"], end, limit, "overtime"))
    return out


def driver_utilization(day: data.Day) -> float:
    """Driving time / duty span across today's working duties, in %."""
    working = day.working_duties()
    span = sum(d["spanMinutes"] for d in working)
    return round(100 * sum(d["drivingMinutes"] for d in working) / span, 1) if span else 0.0


def _recommended_route(windows: list[Window]) -> str | None:
    for cand in data.express_candidates():
        rt = 2 * cand["tripDurationMin"] + cand["turnaroundMin"]
        for s in data.express_departures(cand):
            if any(w.station == cand["startStation"] and w.fits(s, s + rt) for w in windows):
                return cand["routeId"]
    return None


@dataclass
class DriverProfile:
    driver_id: str
    home_station: str
    duty_start: int
    duty_end: int
    driving_minutes: int
    windows: list[Window]
    headroom_minutes: int  # maxShiftHours minus duty span

    @property
    def idle_minutes(self) -> int:
        return sum(w.minutes for w in self.windows)

    @property
    def free_capacity_minutes(self) -> int:
        return self.idle_minutes + self.headroom_minutes


def driver_profiles(day: data.Day) -> list[DriverProfile]:
    """Driving time, idle gaps and spare shift capacity for every driver working on `day`."""
    trips = data.trips_by_duty()
    drivers = data.drivers()
    by_driver: dict[str, list[Window]] = {}
    for w in idle_windows(day):
        by_driver.setdefault(w.driver_id, []).append(w)

    out = []
    for duty in sorted(day.working_duties(), key=lambda d: d["driverId"]):
        drv = drivers[duty["driverId"]]
        legs = trips[duty["dutyId"]]
        start, end = to_min(legs[0]["departureTime"]), to_min(legs[-1]["arrivalTime"])
        out.append(DriverProfile(
            driver_id=drv["driverId"],
            home_station=drv["homeStation"],
            duty_start=start,
            duty_end=end,
            driving_minutes=sum(to_min(t["arrivalTime"]) - to_min(t["departureTime"]) for t in legs),
            windows=by_driver.get(drv["driverId"], []),
            headroom_minutes=max(0, round(drv["maxShiftHours"] * 60) - (end - start)),
        ))
    return out


def get_idle_drivers(date: str | None) -> IdleDriversResponse:
    day = data.resolve_day(date, default=tomorrow())
    profiles = driver_profiles(day)
    rows = [
        IdleDriver(
            driver_id=p.driver_id,
            home_station=p.home_station,
            duty_start=to_hhmm(p.duty_start),
            duty_end=to_hhmm(p.duty_end),
            driving_hours=hours(p.driving_minutes),
            idle_hours=hours(p.idle_minutes),
            free_capacity_hours=hours(p.free_capacity_minutes),
            idle_windows=[IdleWindow(start=to_hhmm(w.start), end=to_hhmm(w.end), station=w.station) for w in p.windows],
            recommended_route=_recommended_route(p.windows),
        )
        for p in profiles
    ]
    return IdleDriversResponse(
        date=day.date,
        total_drivers=len(data.drivers()),
        working_drivers=len(profiles),
        idle_driver_count=sum(1 for p in profiles if p.windows),
        total_idle_hours=hours(sum(p.idle_minutes for p in profiles)),
        total_free_capacity_hours=hours(sum(p.free_capacity_minutes for p in profiles)),
        drivers=rows,
    )
