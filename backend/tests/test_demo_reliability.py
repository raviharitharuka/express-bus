"""Demo reliability: reset restores original results, /optimize time limit + cached fallback, data notes.

Run from backend/ with  python -m pytest -q
"""

import pytest

import config
from schemas.optimize import OptimizeRequest
from services import data, express_model, optimizer
from services.optimizer import optimize
from tests.test_contract import client

DATE = "2026-10-05"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("DEMO_DATE", DATE)
    monkeypatch.setenv("DEMO_TIME", "09:15")
    monkeypatch.delenv(optimizer.TIME_LIMIT_ENV, raising=False)
    data.reset_live_state()
    optimizer.clear_cache()
    yield
    data.reset_live_state()
    optimizer.clear_cache()


def run_optimize(**body):
    r = client.post("/optimize", json={"date": DATE, **body})
    return r.status_code, r.json()


# --- POST /admin/reset returns exactly to the original results ---------------------

def test_reset_restores_the_original_optimize_result():
    status, before = run_optimize()
    assert status == 200 and "D002" in {a["driver"] for r in before["recommendations"] for a in r["assignments"]}

    assert client.patch("/admin/drivers/D002", json={"available": False}).status_code == 200
    em = client.post("/emergency", json={"incidentType": "BREAKDOWN", "busId": "B021", "station": "Airport",
                                         "time": "09:15"}).json()
    assert em["status"] == "DISPATCHED"
    _, changed = run_optimize()
    assert changed != before  # both changes are live

    assert client.post("/admin/reset").json()["overridesActive"] == 0
    _, after = run_optimize()
    assert after == before
    assert data.buses() == data._load("buses.json")["buses"]  # emergency bus pool changes are gone too


# --- Time limit -------------------------------------------------------------------

def capture_time_limits(monkeypatch):
    seen = []
    real = optimizer.solve

    def spy(*args, time_limit_s):
        seen.append(time_limit_s)
        return real(*args, time_limit_s=time_limit_s)

    monkeypatch.setattr(optimizer, "solve", spy)
    return seen


@pytest.mark.parametrize("env,expected", [(None, 8.0), ("3", 3.0), ("2.5", 2.5), ("abc", 8.0), ("0", 8.0), ("-1", 8.0)])
def test_time_limit_comes_from_env(monkeypatch, env, expected):
    if env is not None:
        monkeypatch.setenv(optimizer.TIME_LIMIT_ENV, env)
    assert optimizer.time_limit_s() == expected


def test_all_solves_share_one_budget(monkeypatch):
    monkeypatch.setenv(optimizer.TIME_LIMIT_ENV, "3")
    seen = capture_time_limits(monkeypatch)
    run_optimize()
    assert len(seen) > 1 and all(0 < t <= 3 for t in seen)
    assert seen == sorted(seen, reverse=True)  # each solve gets what's left of the same deadline


# --- Cached fallback --------------------------------------------------------------

def test_solver_failure_returns_the_cached_result(monkeypatch):
    _, first = run_optimize()
    assert first["cached"] is False

    def broken(*args, **kwargs):
        raise RuntimeError("solver crashed")

    monkeypatch.setattr(optimizer, "solve", broken)
    status, second = run_optimize()
    assert status == 200 and second["cached"] is True
    assert {**second, "cached": False} == first


def test_timeout_status_returns_the_cached_result(monkeypatch):
    _, first = run_optimize()
    real = optimizer.solve

    def cut_short(*args, **kwargs):
        sol = real(*args, **kwargs)
        sol.status = "FEASIBLE"  # what CP-SAT reports when the time limit stops it before proving optimality
        return sol

    monkeypatch.setattr(optimizer, "solve", cut_short)
    _, second = run_optimize()
    assert second["cached"] is True and {**second, "cached": False} == first


def test_real_time_limit_hit_returns_the_cached_result(monkeypatch):
    _, first = run_optimize()
    monkeypatch.setenv(optimizer.TIME_LIMIT_ENV, "0.000001")  # one microsecond: the deadline passes at once
    _, second = run_optimize()
    assert second["cached"] is True and {**second, "cached": False} == first


def test_no_cached_result_gives_503_and_the_dashboard_still_loads(monkeypatch):
    monkeypatch.setenv(optimizer.TIME_LIMIT_ENV, "0.000001")
    status, body = run_optimize()
    assert status == 503 and body["error"] == "OPTIMIZE_UNAVAILABLE"
    dash = client.get("/dashboard")
    assert dash.status_code == 200 and dash.json()["recommendation"]["title"] == "Optimization unavailable"


def test_cache_is_per_date_and_options(monkeypatch):
    run_optimize()  # caches 2026-10-05 with default options
    monkeypatch.setenv(optimizer.TIME_LIMIT_ENV, "0.000001")
    assert run_optimize()[1]["cached"] is True
    assert run_optimize(allowOvertime=False)[0] == 503  # different options
    assert client.post("/optimize", json={"date": "2026-10-06"}).status_code == 503  # different date


def test_cache_is_per_data_source(monkeypatch):
    run_optimize()  # synthetic
    data.switch_source("gtfs")
    try:
        monkeypatch.setenv(optimizer.TIME_LIMIT_ENV, "0.000001")
        assert run_optimize()[0] == 503
    finally:
        data.switch_source("synthetic")


def test_validation_errors_are_not_hidden_by_the_cache(monkeypatch):
    run_optimize()
    monkeypatch.setenv(optimizer.TIME_LIMIT_ENV, "0.000001")
    status, body = run_optimize(candidates=[{"startStation": "Mars", "endStation": "Airport", "headwayMin": 30,
                                             "serviceStart": "10:00", "serviceEnd": "12:00", "tripDurationMin": 15}])
    assert status == 404 and body["error"] == "STATION_NOT_FOUND"


# --- dataSource and dataNote --------------------------------------------------------

def test_health_and_admin_status_report_source_and_note():
    health, status = client.get("/health").json(), client.get("/admin/status").json()
    for body in (health, status):
        assert body["dataSource"] == config.DATA_SOURCE and body["dataNote"] == config.DATA_NOTE
    data.switch_source("gtfs")
    try:
        health, status = client.get("/health").json(), client.get("/admin/status").json()
        assert health["dataNote"] == status["dataNote"] == config.DATA_NOTES["gtfs"]
    finally:
        data.switch_source("synthetic")
