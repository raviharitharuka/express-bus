"""Emergency recovery: run from backend/ with  python -m pytest -q"""

import pytest

from schemas.emergency import EmergencyRequest
from services import data
from services.emergency import handle_incident
from errors import ApiError


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setenv("DEMO_DATE", "2026-10-05")
    data.reset_live_state()
    yield
    data.reset_live_state()


def breakdown(bus="B021", station="Airport", time="09:15"):
    return handle_incident(EmergencyRequest(incident_type="BREAKDOWN", bus_id=bus, station=station, time=time))


def test_airport_breakdown_uses_nearest_station_with_spare_bus():
    res = breakdown()
    assert res.status == "DISPATCHED"
    assert res.source_station == "North Station"  # Airport has 0 spares; North is 4 km away
    assert res.replacement_bus == "B027"  # first spare at North Station
    assert res.driver == "D011"  # idle at North Station 08:50-12:30
    assert res.eta_minutes > 0 and res.timeline[-1].time >= "09:15"


def test_broken_bus_leaves_pool_and_replacement_moves():
    res = breakdown()
    buses = {b["busId"]: b for b in data.buses()}
    assert buses["B021"]["status"] == "maintenance"
    assert buses[res.replacement_bus]["status"] == "active"
    assert buses[res.replacement_bus]["station"] == "Airport"


def test_driver_is_on_shift_for_the_whole_recovery():
    res = breakdown()
    day = data.resolve_day("2026-10-05")
    duty = next(d for d in day.working_duties() if d["driverId"] == res.driver)
    arrival = res.timeline[-1].time
    assert duty["start"] <= "09:15" and arrival <= duty["end"]


def test_second_incident_sees_reduced_pool_and_busy_driver():
    first = breakdown("B021")
    second = breakdown("B020")
    assert second.replacement_bus != first.replacement_bus
    assert second.driver != first.driver


def test_no_bus_available_is_graceful():
    for b in data.buses():
        if b["status"] == "spare":
            data.update_bus(b["busId"], status="active")
    res = breakdown()
    assert res.status == "NO_BUS_AVAILABLE"
    assert res.replacement_bus is None and res.eta_minutes is None
    assert "Dispatcher action" in res.timeline[-1].step


def test_no_driver_available_is_graceful():
    res = breakdown(time="03:00")  # nobody on shift at night
    assert res.status == "NO_DRIVER_AVAILABLE"
    assert res.driver is None


def test_errors():
    with pytest.raises(ApiError) as e:
        breakdown(bus="B099")
    assert e.value.status == 404
    breakdown()
    with pytest.raises(ApiError) as e:
        breakdown()  # B021 is already broken
    assert e.value.status == 409


def test_what_if_does_not_change_the_pool():
    with data.what_if():
        breakdown()
    assert next(b for b in data.buses() if b["busId"] == "B021")["status"] == "active"
