"""Loads the hardcoded MVP dataset from backend/data/ (cached), plus live fleet changes made by emergencies.

Live changes are kept in memory only: restarting the server or POST /emergency/reset clears them.
"""

import copy
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

import config
from errors import ApiError
from services.time_utils import to_min, today

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# File used for each logical data file, per DATA_SOURCE. The gtfs names say what's in them:
# *_gtfs.json mix real GTFS trips/stops/lines with synthetic parts (see their "provenance" key);
# *_gtfs_synthetic.json are fully synthetic rosters, because GTFS has no driver or bus data.
DATA_FILES = {
    "synthetic": {name: name for name in ("timetable.json", "stations.json", "drivers.json", "buses.json", "routes.json")},
    "gtfs": {
        "timetable.json": "timetable_gtfs.json",
        "stations.json": "stations_gtfs.json",
        "routes.json": "routes_gtfs.json",
        "drivers.json": "drivers_gtfs_synthetic.json",
        "buses.json": "buses_gtfs_synthetic.json",
    },
}


def _path(name: str) -> Path:
    """The file DATA_SOURCE selects for `name`; the services never see the difference."""
    return DATA_DIR / DATA_FILES[config.DATA_SOURCE][name]


@cache
def _load(name: str) -> dict:
    return json.loads(_path(name).read_text())


def preload() -> None:
    """Load every data file once at startup so a missing file fails fast."""
    for name in DATA_FILES[config.DATA_SOURCE]:
        if not _path(name).exists():
            raise RuntimeError(f"DATA_SOURCE={config.DATA_SOURCE} needs {_path(name).name}; "
                               "run scripts/build_real_timetable.py")
        _load(name)


def stations() -> list[dict]:
    return _load("stations.json")["stations"]


def station_names() -> list[str]:
    return [s["name"] for s in stations()]


def distance_km(a: str, b: str) -> int:
    return _load("stations.json")["distanceKm"][a][b]


def drivers() -> dict[str, dict]:
    return {d["driverId"]: d for d in _load("drivers.json")["drivers"]}


def buses() -> list[dict]:
    """Buses with any live changes (breakdowns, relocations) applied."""
    return [{**b, **_bus_changes.get(b["busId"], {})} for b in _load("buses.json")["buses"]]


def routes() -> dict[str, dict]:
    return {r["routeId"]: r for r in _load("routes.json")["routes"]}


def express_candidates() -> list[dict]:
    return _load("routes.json")["expressCandidates"]


def express_departures(cand: dict) -> list[int]:
    """Departure minutes from the start station: every headway, from serviceStart until before serviceEnd."""
    return list(range(to_min(cand["serviceStart"]), to_min(cand["serviceEnd"]), cand["headwayMin"]))


def spare_buses(station: str) -> list[str]:
    return [b["busId"] for b in buses() if b["station"] == station and b["status"] == "spare"]


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
        raise ApiError(400, "INVALID_DATE", f"Date '{value}' must be a valid YYYY-MM-DD date")
    iso = d.isoformat()
    entry = next((c for c in calendar() if c["date"] == iso), None)
    if entry:
        return Day(iso, entry["dayType"], set(entry["driversOnVacation"]))
    day_type = "sunday" if d.weekday() == 6 else "saturday" if d.weekday() == 5 else "weekday"
    on_vacation = {did for did, drv in drivers().items() if iso in drv["vacationDates"]}
    return Day(iso, day_type, on_vacation)


# --- Live state (in memory) -------------------------------------------------

_bus_changes: dict[str, dict] = {}  # busId -> overridden fields, e.g. {"status": "maintenance"}
_driver_busy_until: dict[str, int] = {}  # driverId -> minute they're free again


def update_bus(bus_id: str, **fields) -> None:
    _bus_changes.setdefault(bus_id, {}).update(fields)


def mark_driver_busy(driver_id: str, until: int) -> None:
    _driver_busy_until[driver_id] = until


def driver_busy_until(driver_id: str) -> int:
    return _driver_busy_until.get(driver_id, -1)


@contextmanager
def what_if():
    """Run hypothetical changes (e.g. a Lotse "what happens if...") and roll them back afterwards."""
    saved = copy.deepcopy(_bus_changes), dict(_driver_busy_until)
    try:
        yield
    finally:
        reset_live_state()
        _bus_changes.update(saved[0])
        _driver_busy_until.update(saved[1])


def reset_live_state() -> None:
    _bus_changes.clear()
    _driver_busy_until.clear()
