"""DATA_SOURCE switches every data file to its _real twin without touching the services."""

import pytest

import config
from schemas.optimize import OptimizeRequest
from services import data
from services.dashboard import get_dashboard
from services.idle import get_idle_drivers
from services.optimizer import optimize


@pytest.fixture
def real_data(monkeypatch):
    monkeypatch.setattr(config, "DATA_SOURCE", "real")
    data._load.cache_clear()
    data.reset_live_state()
    yield
    data._load.cache_clear()
    data.reset_live_state()


def test_synthetic_is_the_default_for_tests():
    assert config.DATA_SOURCE == "synthetic"
    assert data._path("timetable.json").name == "timetable.json"
    assert len(data.station_names()) == 5


def test_real_files_load_and_services_run(real_data):
    data.preload()
    assert all(data._path(n).name.endswith("_real.json") for n in data.DATA_FILES)
    assert len(data.station_names()) > 5
    assert set(data.drivers()) >= {d["driverId"] for d in data.duties()}  # every duty's driver exists
    assert get_idle_drivers("2026-07-01").working_drivers == len(data.duties())
    assert optimize(OptimizeRequest(date="2026-07-01")).recommendations
    assert get_dashboard("2026-07-01").kpis.available_buses > 0


# --- /idle-drivers and /optimize over HTTP on real data, checked against API_CONTRACT.md ----------

from tests.test_contract import _check_tables, _compare, _json_blocks, _response_part, _section, client  # noqa: E402

REAL_DATE = "2026-07-01"


def _contract_example(heading: str) -> tuple[dict, str]:
    part = _response_part(_section(heading))
    return _json_blocks(part)[0], part


@pytest.mark.parametrize("params", [{}, {"date": REAL_DATE}])
def test_real_idle_drivers_matches_contract(real_data, monkeypatch, params):
    monkeypatch.setenv("DEMO_DATE", "2026-06-30")  # default date = tomorrow = the real service date
    r = client.get("/idle-drivers", params=params)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["date"] == REAL_DATE and body["idleDriverCount"] > 0
    example, part = _contract_example("## 1. `GET /idle-drivers`")
    _compare(example, body)
    _check_tables(part, body)


@pytest.mark.parametrize("payload", [
    None,
    {"date": REAL_DATE},
    {"date": REAL_DATE, "candidates": [{
        "startStation": "Nürnberg, Frankenstraße", "endStation": "Nürnberg Röthenbach",
        "headwayMin": 60, "serviceStart": "9:00", "serviceEnd": "12:00", "tripDurationMin": 15}]},
])
def test_real_optimize_matches_contract(real_data, monkeypatch, payload):
    monkeypatch.setenv("DEMO_DATE", "2026-06-30")
    r = client.post("/optimize", json=payload) if payload is not None else client.post("/optimize")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["date"] == REAL_DATE and body["recommendations"]
    example, part = _contract_example("## 2. `POST /optimize`")
    _compare(example, body)
    _check_tables(part, body)
    for rec in body["recommendations"]:  # every assigned driver is a real-data driver working that day
        drivers = {a["driver"] for a in rec["assignments"] if a["driver"] and not a["driver"].startswith("NEW-")}
        assert drivers <= set(data.drivers())


def test_overtime_starts_where_the_duty_ends(real_data):
    from services.idle import overtime_windows
    day = data.resolve_day(REAL_DATE)
    trips = data.trips_by_duty()
    last_stop = {d["driverId"]: trips[d["dutyId"]][-1]["endStation"] for d in day.working_duties()}
    windows = overtime_windows(day)
    assert windows and all(w.station == last_stop[w.driver_id] for w in windows)
