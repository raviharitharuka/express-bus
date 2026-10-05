"""Loads the hardcoded MVP dataset from backend/data/ (read-only, cached)."""

import json
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from errors import ApiError
from services.time_utils import today

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@cache
def _load(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text())


def stations() -> list[dict]:
    return _load("stations.json")["stations"]


def station_names() -> list[str]:
    return [s["name"] for s in stations()]


def distance_km(a: str, b: str) -> int:
    return _load("stations.json")["distanceKm"][a][b]


def drivers() -> dict[str, dict]:
    return {d["driverId"]: d for d in _load("drivers.json")["drivers"]}


def buses() -> list[dict]:
    return _load("buses.json")["buses"]


def routes() -> dict[str, dict]:
    return {r["routeId"]: r for r in _load("routes.json")["routes"]}


def express_candidates() -> list[dict]:
    return _load("routes.json")["expressCandidates"]


def duties() -> list[dict]:
    return _load("timetable.json")["duties"]


def trips_by_duty() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for t in _load("timetable.json")["trips"]:
        out.setdefault(t["dutyId"], []).append(t)
    return out


def calendar() -> list[dict]:
    return _load("timetable.json")["calendar"]


def require_station(name: str) -> str:
    if name not in station_names():
        raise ApiError(404, "STATION_NOT_FOUND", f"Unknown station '{name}'. Use one of: {', '.join(station_names())}")
    return name


@dataclass
class Day:
    date: str
    day_type: str  # weekday | saturday | sunday
    on_vacation: set[str]

    def working_duties(self) -> list[dict]:
        """Duties that run today and whose driver isn't on vacation."""
        return [d for d in duties() if self.day_type in d["runsOn"] and d["driverId"] not in self.on_vacation]


def resolve_day(value: str | None = None, default: date | None = None) -> Day:
    """Calendar day for `value`; dates outside the 30-day calendar fall back to the weekday rules."""
    try:
        d = date.fromisoformat(value) if value else (default or today())
    except ValueError:
        raise ApiError(400, "INVALID_DATE", f"Date '{value}' must be YYYY-MM-DD")
    iso = d.isoformat()
    entry = next((c for c in calendar() if c["date"] == iso), None)
    if entry:
        return Day(iso, entry["dayType"], set(entry["driversOnVacation"]))
    day_type = "sunday" if d.weekday() == 6 else "saturday" if d.weekday() == 5 else "weekday"
    on_vacation = {did for did, drv in drivers().items() if iso in drv["vacationDates"]}
    return Day(iso, day_type, on_vacation)
