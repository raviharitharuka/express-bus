"""Admin endpoints and the overrides layer: run from backend/ with  python -m pytest -q"""

import json
from pathlib import Path

import pytest

import config
from services import admin, data
from tests.test_contract import _compare, client

MOCKS = Path(__file__).resolve().parents[2] / "frontend" / "public" / "mock" / "admin"
DATE = "2026-10-05"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("DEMO_DATE", DATE)
    monkeypatch.setenv("DEMO_TIME", "09:15")
    data.reset_live_state()
    admin.record_optimize_ms(None)
    yield
    if config.DATA_SOURCE != "synthetic":
        data.switch_source("synthetic")
    data.reset_live_state()


def optimize():
    r = client.post("/optimize", json={"date": DATE})
    assert r.status_code == 200
    return r.json()


@pytest.mark.parametrize("path,mock", [
    ("/admin/status", "status"), ("/admin/drivers", "drivers"), ("/admin/buses", "buses"),
    ("/admin/stations", "stations"), ("/admin/routes", "routes"),
])
def test_responses_match_the_mocks(path, mock):
    r = client.get(path)
    assert r.status_code == 200
    expected = json.loads((MOCKS / f"{mock}.json").read_text())
    _compare(expected, r.json())
    if mock != "status":  # lastOptimizeMs differs; the lists are the default synthetic data exactly
        assert r.json() == expected


def test_unavailable_driver_changes_optimize_and_reset_restores_it():
    before = optimize()
    assert "D002" in {a["driver"] for r in before["recommendations"] for a in r["assignments"]}

    r = client.patch("/admin/drivers/D002", json={"available": False})
    assert r.status_code == 200 and r.json()["available"] is False and r.json()["dutyId"] is None
    after = optimize()
    assert "D002" not in {a["driver"] for r in after["recommendations"] for a in r["assignments"]}
    assert after != before

    status = client.post("/admin/reset").json()
    assert status["overridesActive"] == 0 and status["lastOptimizeMs"] is None
    assert optimize() == before


def test_status_tracks_overrides_and_optimize_time():
    assert client.get("/admin/status").json()["lastOptimizeMs"] is None
    optimize()
    assert isinstance(client.get("/admin/status").json()["lastOptimizeMs"], int)
    client.patch("/admin/drivers/D001", json={"overtimeAvailable": False})
    client.patch("/admin/buses/B001", json={"status": "maintenance"})
    assert client.get("/admin/status").json()["overridesActive"] == 2


def test_overrides_reach_idle_dashboard_and_emergency():
    idle_before = client.get(f"/idle-drivers?date={DATE}").json()["idleDriverCount"]
    spare_before = client.get("/dashboard").json()["kpis"]["availableBuses"]
    client.patch("/admin/drivers/D011", json={"available": False})
    client.patch("/admin/buses/B027", json={"status": "broken"})
    assert client.get(f"/idle-drivers?date={DATE}").json()["idleDriverCount"] == idle_before - 1
    assert client.get("/dashboard").json()["kpis"]["availableBuses"] == spare_before - 1
    em = client.post("/emergency", json={"incidentType": "BREAKDOWN", "busId": "B021", "station": "Airport",
                                         "time": "09:15"}).json()
    assert em["replacementBus"] != "B027" and em["driver"] != "D011"


def test_unavailable_driver_is_off_on_every_date():
    client.patch("/admin/drivers/D002", json={"available": False})
    for date in (DATE, "2026-10-06", "2026-10-20"):  # today, /optimize's default (tomorrow), later
        assert "D002" not in {d["driverId"] for d in data.resolve_day(date).working_duties()}
    default = client.post("/optimize").json()  # no date: tomorrow
    assert "D002" not in {a["driver"] for r in default["recommendations"] for a in r["assignments"]}


def test_vacation_override_counts_for_shortages():
    # D009, D014, D019 are away on 2026-10-22 (3 missing); add D001 that day -> 4
    client.patch("/admin/drivers/D001", json={"vacationDates": ["2026-10-22"]})
    alert = [a["message"] for a in client.get("/dashboard").json()["alerts"] if "short" in a["message"]]
    assert alert == ["4 driver(s) short predicted on 2026-10-22"]


def test_bus_available_returns_to_its_role():
    client.patch("/admin/buses/B021", json={"status": "broken"})  # B021 has a duty
    client.patch("/admin/buses/B027", json={"status": "broken"})  # B027 is a spare
    assert client.patch("/admin/buses/B021", json={"status": "available"}).json()["status"] == "active"
    assert client.patch("/admin/buses/B027", json={"status": "available"}).json()["status"] == "spare"
    moved = client.patch("/admin/buses/B027", json={"station": "Airport"}).json()
    assert moved["station"] == "Airport" and moved["overridden"]


def test_emergency_reset_keeps_admin_edits():
    client.patch("/admin/buses/B027", json={"station": "Airport"})
    client.post("/emergency", json={"incidentType": "BREAKDOWN", "busId": "B021", "station": "Airport", "time": "09:15"})
    client.post("/emergency/reset")
    buses = {b["busId"]: b for b in data.buses()}
    assert buses["B027"]["station"] == "Airport"  # admin edit kept
    assert buses["B021"]["status"] == "active"  # breakdown undone


def test_files_on_disk_never_change():
    before = {p.name: p.read_bytes() for p in data.DATA_DIR.glob("*.json")}
    client.patch("/admin/drivers/D001", json={"maxShiftHours": 8.5, "vacationDates": ["2026-10-07"]})
    client.patch("/admin/buses/B001", json={"status": "broken", "station": "University"})
    optimize()
    client.post("/admin/reset")
    assert {p.name: p.read_bytes() for p in data.DATA_DIR.glob("*.json")} == before


def test_fractional_max_shift_works_in_the_solver():
    client.patch("/admin/drivers/D020", json={"maxShiftHours": 8.5, "overtimeAvailable": True})
    assert optimize()["recommendations"]


def test_pagination_and_search():
    page = client.get("/admin/buses?page=3&pageSize=20").json()
    assert (page["page"], page["pageSize"], page["total"], len(page["items"])) == (3, 20, 50, 10)
    assert client.get("/admin/buses?page=9").json()["items"] == []
    assert [s["name"] for s in client.get("/admin/stations?q=NORTH").json()["items"]] == ["North Station"]
    assert {r["routeId"] for r in client.get("/admin/routes?q=airport").json()["items"]} == {"R1", "R5", "R6", "R7"}
    assert client.get("/admin/drivers?q=university").json()["total"] == 3


def test_data_source_switch_reloads_and_clears_overrides():
    client.patch("/admin/drivers/D001", json={"available": False})
    status = client.post("/admin/data-source", json={"dataSource": "gtfs"}).json()
    assert status["dataSource"] == "gtfs" and status["overridesActive"] == 0
    assert status["counts"]["stations"] > 5 and client.get("/health").json()["dataSource"] == "gtfs"
    back = client.post("/admin/data-source", json={"dataSource": "synthetic"}).json()
    assert back["counts"] == {"stations": 5, "drivers": 20, "buses": 50, "routes": 10, "trips": 144}
    assert data.drivers()["D001"]["available"] is True


@pytest.mark.parametrize("method,path,body,status,error", [
    ("patch", "/admin/drivers/D999", {"available": False}, 404, "DRIVER_NOT_FOUND"),
    ("patch", "/admin/buses/B999", {"status": "broken"}, 404, "BUS_NOT_FOUND"),
    ("patch", "/admin/buses/B001", {"station": "Mars"}, 404, "STATION_NOT_FOUND"),
    ("patch", "/admin/drivers/D001", {}, 400, "INVALID_REQUEST"),
    ("patch", "/admin/drivers/D001", {"maxShiftHours": 20}, 400, "INVALID_REQUEST"),
    ("patch", "/admin/drivers/D001", {"vacationDates": ["2026-13-01"]}, 400, "INVALID_REQUEST"),
    ("patch", "/admin/drivers/D001", {"availble": False}, 400, "INVALID_REQUEST"),
    ("patch", "/admin/buses/B001", {"status": "sold"}, 400, "INVALID_REQUEST"),
    ("post", "/admin/data-source", {"dataSource": "real"}, 400, "INVALID_REQUEST"),
    ("get", "/admin/drivers?pageSize=500", None, 400, "INVALID_REQUEST"),
])
def test_errors(method, path, body, status, error):
    r = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
    assert r.status_code == status and r.json()["error"] == error


def test_missing_gtfs_files_give_409(monkeypatch):
    monkeypatch.setitem(data.DATA_FILES, "gtfs", {**data.DATA_FILES["gtfs"], "timetable.json": "nope.json"})
    r = client.post("/admin/data-source", json={"dataSource": "gtfs"})
    assert r.status_code == 409 and r.json()["error"] == "DATA_SOURCE_UNAVAILABLE"
    assert config.DATA_SOURCE == "synthetic"
