"""The data every engine reads: the JSON files in backend/data/ (cached) plus an in-memory overrides layer.

Overrides come from two sources and are never written to disk:
- admin:     PATCH /admin/drivers/{id}, PATCH /admin/buses/{id}
- emergency: breakdowns and dispatches from POST /emergency
POST /admin/reset clears both, POST /emergency/reset only the emergency ones, a restart or a data-source
switch everything. All services go through the accessors below, so overrides change their results.
"""

import copy
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
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
    """Drivers with admin overrides applied; `available` is False for drivers on sick leave today."""
    return {d["driverId"]: {**d, "available": True, **_driver_changes.get(d["driverId"], {})}
            for d in _load("drivers.json")["drivers"]}


def buses() -> list[dict]:
    """Buses with overrides applied (admin edits, breakdowns, relocations)."""
    return [{**b, **{field: stack[-1][1] for field, stack in _bus_changes.get(b["busId"], {}).items()}}
            for b in _load("buses.json")["buses"]]


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
    sick: set[str] = field(default_factory=set)  # available=False; only applies to today

    def active_duties(self) -> list[dict]:
        """Duties scheduled for this day type, whoever is driving."""
        return [d for d in duties() if self.day_type in d["runsOn"]]

    def working_duties(self) -> list[dict]:
        """Duties that run today and whose driver isn't on vacation or sick."""
        absent = self.on_vacation | self.sick
        return [d for d in self.active_duties() if d["driverId"] not in absent]

    def uncovered_duties(self) -> list[dict]:
        absent = self.on_vacation | self.sick
        return [d for d in self.active_duties() if d["driverId"] in absent]


def resolve_day(value: str | None = None, default: date | None = None) -> Day:
    """Calendar day for `value`; dates outside the 30-day calendar fall back to the weekday rules."""
    try:
        d = date.fromisoformat(value) if value else (default or today())
    except ValueError:
        raise ApiError(400, "INVALID_DATE", f"Date '{value}' must be a valid YYYY-MM-DD date")
    iso = d.isoformat()
    entry = next((c for c in calendar() if c["date"] == iso), None)
    if entry:  # the calendar gives the day type (holidays); vacations come from drivers() so overrides count
        day_type = entry["dayType"]
    else:
        day_type = "sunday" if d.weekday() == 6 else "saturday" if d.weekday() == 5 else "weekday"
    roster = drivers()
    on_vacation = {did for did, drv in roster.items() if iso in drv["vacationDates"]}
    sick = {did for did, drv in roster.items() if not drv["available"]} if iso == today().isoformat() else set()
    return Day(iso, day_type, on_vacation, sick)


# --- Overrides layer (in memory) -------------------------------------------------

# busId -> field -> [(source, value), ...]: newest last. Keeping the stack means undoing an emergency
# falls back to an earlier admin edit of the same field instead of the file value.
_bus_changes: dict[str, dict[str, list[tuple[str, object]]]] = {}
_driver_changes: dict[str, dict] = {}  # driverId -> admin-overridden fields
_driver_busy_until: dict[str, int] = {}  # driverId -> minute they're free again (emergency dispatches)


def update_bus(bus_id: str, source: str = "emergency", **fields) -> None:
    changes = _bus_changes.setdefault(bus_id, {})
    for name, value in fields.items():
        changes.setdefault(name, []).append((source, value))


def update_driver(driver_id: str, **fields) -> None:
    _driver_changes.setdefault(driver_id, {}).update(fields)


def mark_driver_busy(driver_id: str, until: int) -> None:
    _driver_busy_until[driver_id] = until


def driver_busy_until(driver_id: str) -> int:
    return _driver_busy_until.get(driver_id, -1)


def overridden_drivers() -> set[str]:
    return set(_driver_changes) | set(_driver_busy_until)


def overridden_buses() -> set[str]:
    return set(_bus_changes)


@contextmanager
def what_if():
    """Run hypothetical changes (e.g. a Lotse "what happens if...") and roll them back afterwards."""
    saved = copy.deepcopy((_bus_changes, _driver_changes, _driver_busy_until))
    try:
        yield
    finally:
        reset_live_state()
        _bus_changes.update(saved[0])
        _driver_changes.update(saved[1])
        _driver_busy_until.update(saved[2])


def reset_emergency_changes() -> None:
    """Undo breakdowns and dispatches; admin edits stay."""
    for bus_id in list(_bus_changes):
        kept = {f: [c for c in stack if c[0] != "emergency"] for f, stack in _bus_changes[bus_id].items()}
        kept = {f: stack for f, stack in kept.items() if stack}
        if kept:
            _bus_changes[bus_id] = kept
        else:
            del _bus_changes[bus_id]
    _driver_busy_until.clear()


def reset_live_state() -> None:
    """Clear every override: admin edits and emergency changes."""
    _bus_changes.clear()
    _driver_changes.clear()
    _driver_busy_until.clear()


def switch_source(name: str) -> None:
    """Load another dataset at runtime: check its files, swap, drop the cache and all overrides."""
    missing = [f for f in DATA_FILES[name].values() if not (DATA_DIR / f).exists()]
    if missing:
        raise ApiError(409, "DATA_SOURCE_UNAVAILABLE",
                       f"DATA_SOURCE={name} needs {', '.join(missing)}; run scripts/build_real_timetable.py")
    config.DATA_SOURCE, config.DATA_NOTE = name, config.DATA_NOTES[name]
    _load.cache_clear()
    reset_live_state()
    preload()
