"""Dashboard KPIs and Lotse intents: run from backend/ with  python -m pytest -q"""

import pytest

from schemas.lotse import LotseRequest
from schemas.emergency import EmergencyRequest
from services import data
from services.lotse import ask
from services.dashboard import get_dashboard
from services.emergency import handle_incident
from services.idle import get_idle_drivers

DATE = "2026-10-05"


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setenv("DEMO_DATE", DATE)
    data.reset_live_state()
    yield
    data.reset_live_state()


def test_dashboard_kpis_come_from_the_services():
    d = get_dashboard(DATE)
    idle = get_idle_drivers(DATE)
    assert d.kpis.available_drivers == idle.idle_driver_count == 10
    assert d.kpis.available_buses == sum(s.available_buses for s in d.stations) == 26
    assert d.kpis.fleet_utilization == 40.0  # 20 of 50 buses on today's duties
    assert d.kpis.additional_routes_identified == 2  # E1 + E3 from /optimize
    assert sum(s.total_buses for s in d.stations) == 50


def test_dashboard_follows_live_breakdowns():
    handle_incident(EmergencyRequest(incident_type="BREAKDOWN", bus_id="B021", station="Airport", time="09:15"))
    d = get_dashboard(DATE)
    assert d.kpis.available_buses == 25  # replacement left the spare pool
    assert d.kpis.fleet_utilization == 40.0  # broken bus out, replacement in
    assert any("B021" in a.message for a in d.alerts)


@pytest.mark.parametrize("question,intent", [
    ("Can we launch a new express route tomorrow?", "launch_route"),
    ("Which drivers are idle?", "idle_drivers"),
    ("Which drivers have unused capacity today?", "idle_drivers"),
    ("What happens if bus B021 breaks down at 09:15?", "breakdown"),
    ("A bus broke down at the University", "breakdown"),
    ("Which station needs more buses?", "station_buses"),
    ("Which station will run out of buses tonight?", "station_buses"),
    ("Are we short of drivers this month?", "driver_shortage"),
])
def test_intents(question, intent):
    r = ask(LotseRequest(question=question))
    assert r.intent == intent
    assert r.answer and r.data is not None
    assert len(r.suggested_questions) == 3


def test_launch_payload_matches_optimizer():
    r = ask(LotseRequest(question="Can we launch a new express route tomorrow?"))
    assert r.data["recommended"] == ["E1", "E3"]
    assert {x["route"] for x in r.data["routes"]} == {"E1", "E2", "E3"}


def test_station_buses_suggests_rebalancing():
    r = ask(LotseRequest(question="Which station needs more buses?"))
    assert r.data["moves"] == [{"from": "North Station", "to": "Airport", "buses": 2, "distanceKm": 4}]
    assert "move 2 buses" in r.answer


def test_breakdown_question_is_hypothetical():
    r = ask(LotseRequest(question="What happens if bus B021 breaks down at 09:15?"))
    assert r.data["hypothetical"] and r.data["status"] == "DISPATCHED"
    assert next(b for b in data.buses() if b["busId"] == "B021")["status"] == "active"


def test_unknown_question_returns_suggestions():
    r = ask(LotseRequest(question="What's the weather like?"))
    assert r.intent == "unknown" and r.data is None
    assert len(r.suggested_questions) == 5
