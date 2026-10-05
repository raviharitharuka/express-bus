"""DATA_SOURCE=gtfs switches every data file to its GTFS-based twin without touching the services."""

import pytest

import config
from schemas.optimize import OptimizeRequest
from services import data
from services.dashboard import get_dashboard
from services.idle import get_idle_drivers
from services.optimizer import optimize


@pytest.fixture
def gtfs_data(monkeypatch):
    monkeypatch.setattr(config, "DATA_SOURCE", "gtfs")
    data._load.cache_clear()
    data.reset_live_state()
    yield
    data._load.cache_clear()
    data.reset_live_state()


def test_synthetic_is_the_default_for_tests():
    assert config.DATA_SOURCE == "synthetic"
    assert data._path("timetable.json").name == "timetable.json"
    assert len(data.station_names()) == 5


def test_gtfs_files_load_and_services_run(gtfs_data):
    data.preload()
    assert data._path("drivers.json").name == "drivers_gtfs_synthetic.json"
    assert data._path("buses.json").name == "buses_gtfs_synthetic.json"
    assert all("gtfs" in data._path(n).name for n in data.DATA_FILES["gtfs"])
    assert len(data.station_names()) > 5
    assert set(data.drivers()) >= {d["driverId"] for d in data.duties()}  # every duty's driver exists
    assert get_idle_drivers("2026-07-01").working_drivers == len(data.duties())
    assert optimize(OptimizeRequest(date="2026-07-01")).recommendations
    assert get_dashboard("2026-07-01").kpis.available_buses > 0


# --- /idle-drivers and /optimize over HTTP on GTFS data, checked against API_CONTRACT.md ----------

from tests.test_contract import _check_tables, _compare, _json_blocks, _response_part, _section, client  # noqa: E402

GTFS_DATE = "2026-07-01"


def _contract_example(heading: str) -> tuple[dict, str]:
    part = _response_part(_section(heading))
    return _json_blocks(part)[0], part


@pytest.mark.parametrize("params", [{}, {"date": GTFS_DATE}])
def test_gtfs_idle_drivers_matches_contract(gtfs_data, monkeypatch, params):
    monkeypatch.setenv("DEMO_DATE", "2026-06-30")  # default date = tomorrow = the real service date
    r = client.get("/idle-drivers", params=params)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["date"] == GTFS_DATE and body["idleDriverCount"] > 0
    example, part = _contract_example("## 1. `GET /idle-drivers`")
    _compare(example, body)
    _check_tables(part, body)


@pytest.mark.parametrize("payload", [
    None,
    {"date": GTFS_DATE},
    {"date": GTFS_DATE, "candidates": [{
        "startStation": "Nürnberg, Frankenstraße", "endStation": "Nürnberg Röthenbach",
        "headwayMin": 60, "serviceStart": "9:00", "serviceEnd": "12:00", "tripDurationMin": 15}]},
])
def test_gtfs_optimize_matches_contract(gtfs_data, monkeypatch, payload):
    monkeypatch.setenv("DEMO_DATE", "2026-06-30")
    r = client.post("/optimize", json=payload) if payload is not None else client.post("/optimize")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["date"] == GTFS_DATE and body["recommendations"]
    example, part = _contract_example("## 2. `POST /optimize`")
    _compare(example, body)
    _check_tables(part, body)
    for rec in body["recommendations"]:  # every assigned driver exists in the GTFS-based roster
        drivers = {a["driver"] for a in rec["assignments"] if a["driver"] and not a["driver"].startswith("NEW-")}
        assert drivers <= set(data.drivers())


def test_overtime_starts_where_the_duty_ends(gtfs_data):
    from services.idle import overtime_windows
    day = data.resolve_day(GTFS_DATE)
    trips = data.trips_by_duty()
    last_stop = {d["driverId"]: trips[d["dutyId"]][-1]["endStation"] for d in day.working_duties()}
    windows = overtime_windows(day)
    assert windows and all(w.station == last_stop[w.driver_id] for w in windows)


def test_every_gtfs_file_says_what_is_synthetic():
    import json
    for name in data.DATA_FILES["gtfs"].values():
        provenance = json.loads((data.DATA_DIR / name).read_text())["provenance"]
        assert provenance["synthetic"], name
        if name.endswith("_synthetic.json"):
            assert provenance["real"] == [], f"{name} is named synthetic but claims real parts"


def test_old_real_value_is_rejected(monkeypatch):
    import importlib
    monkeypatch.setenv("DATA_SOURCE", "real")
    with pytest.raises(RuntimeError, match="renamed to DATA_SOURCE=gtfs"):
        importlib.reload(config)
    monkeypatch.setenv("DATA_SOURCE", "synthetic")
    importlib.reload(config)


def test_health_says_what_is_real(gtfs_data, monkeypatch):
    monkeypatch.setattr(config, "DATA_NOTE", config.DATA_NOTES["gtfs"])
    body = client.get("/health").json()
    assert body["dataSource"] == "gtfs" and "synthetic" in body["dataNote"]


def test_gtfs_timetable_is_clean(gtfs_data):
    """No overlapping or duplicate trips, no empty fields, no unrealistic waits inside a duty."""
    from collections import defaultdict
    from services.time_utils import to_min
    day = data.resolve_day(GTFS_DATE)
    trips_by_duty = data.trips_by_duty()
    trips = [t for d in day.working_duties() for t in trips_by_duty[d["dutyId"]]]

    by_bus = defaultdict(list)
    for t in trips:
        by_bus[t["busId"]].append(t)
    for groups in (trips_by_duty, by_bus):
        for legs in groups.values():
            legs = sorted(legs, key=lambda t: t["departureTime"])
            assert all(to_min(a["arrivalTime"]) <= to_min(b["departureTime"]) for a, b in zip(legs, legs[1:]))

    key = [(t["route"], t["startStation"], t["endStation"], t["departureTime"]) for t in trips]
    assert len(key) == len(set(key)), "duplicate trips"
    rows = trips + day.working_duties() + list(data.drivers().values()) + data.buses() + data.stations()
    assert all(v not in (None, "") for r in rows for v in r.values()), "empty fields"
    assert all(to_min(t["arrivalTime"]) > to_min(t["departureTime"]) for t in trips)

    waits = [to_min(b["departureTime"]) - to_min(a["arrivalTime"])
             for legs in trips_by_duty.values() for a, b in zip(legs, legs[1:])]
    assert max(waits) < 180, "a duty contains a wait of 3 h or more"
