"""Every endpoint matches API_CONTRACT.md.

The JSON examples in the contract are sent as real requests, and each response
is compared with the documented example: same keys, same value types, and every
field named in the response tables exists. Run from backend/ with
python -m pytest -q
"""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from services import data

CONTRACT = (Path(__file__).resolve().parents[2] / "API_CONTRACT.md").read_text()
client = TestClient(app)


def _section(heading: str) -> str:
    start = CONTRACT.index(heading)
    nxt = re.search(r"^## \d", CONTRACT[start + len(heading):], re.M)
    return CONTRACT[start: start + len(heading) + nxt.start()] if nxt else CONTRACT[start:]


def _json_blocks(text: str) -> list[dict]:
    return [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", text, re.S)]


def _response_part(section: str) -> str:
    return section[section.index("**Response `200`**"):]


def _table_fields(text: str) -> list[str]:
    """Backticked names in the first column of markdown tables, e.g. `drivers[].idleHours`."""
    fields = []
    for line in text.splitlines():
        if line.startswith("| `"):
            first = line.split("|")[1]
            fields += re.findall(r"`([A-Za-z\[\]./]+)`", first)
    return fields


def _same_type(expected, actual) -> bool:
    if expected is None or actual is None:
        return True  # nullable fields: examples may show either
    if isinstance(expected, bool) or isinstance(actual, bool):
        return isinstance(expected, bool) and isinstance(actual, bool)
    if isinstance(expected, (int, float)):
        return isinstance(actual, (int, float))
    return type(expected) is type(actual)


def _compare(expected, actual, path="$"):
    assert _same_type(expected, actual), f"{path}: expected {type(expected).__name__}, got {actual!r}"
    if isinstance(expected, dict):
        partial = "..." in expected  # "...": "..." marks an abbreviated example
        exp_keys = set(expected) - {"..."}
        missing = exp_keys - set(actual)
        assert not missing, f"{path}: missing {sorted(missing)}"
        if not partial:
            extra = set(actual) - exp_keys
            assert not extra, f"{path}: undocumented {sorted(extra)}"
        for k in exp_keys:
            _compare(expected[k], actual[k], f"{path}.{k}")
    elif isinstance(expected, list) and expected and actual:
        for item in actual:
            _compare(expected[0], item, f"{path}[]")


def _resolve(obj, path: str) -> bool:
    """Does `a.b[].c` exist in obj (checking every list element)?"""
    parts = re.findall(r"[A-Za-z]+|\[\]", path)
    nodes = [obj]
    for p in parts:
        if p == "[]":
            nodes = [x for n in nodes if isinstance(n, list) for x in n]
            continue
        dicts = [n for n in nodes if isinstance(n, dict)]
        if dicts and not all(p in n for n in dicts):
            return False
        nodes = [n[p] for n in dicts]
    return True


def _check_tables(section_text: str, body: dict):
    for field in _table_fields(section_text):
        for alt in field.split("/"):  # `a` / `b` written as `a/b` is not used, but keep it safe
            assert _resolve(body, alt.strip()), f"table field `{alt}` not in response"


@pytest.fixture(autouse=True)
def demo_clock(monkeypatch):
    monkeypatch.setenv("DEMO_DATE", "2026-10-05")
    monkeypatch.setenv("DEMO_TIME", "09:15")
    data.reset_live_state()
    yield
    data.reset_live_state()


def test_idle_drivers():
    sec = _section("## 1. `GET /idle-drivers`")
    r = client.get("/idle-drivers", params={"date": "2026-10-06"})
    assert r.status_code == 200
    _compare(_json_blocks(_response_part(sec))[0], r.json())
    _check_tables(_response_part(sec), r.json())


def test_optimize():
    sec = _section("## 2. `POST /optimize`")
    request = _json_blocks(sec)[0]
    r = client.post("/optimize", json=request)
    assert r.status_code == 200, r.text
    _compare(_json_blocks(_response_part(sec))[0], r.json())
    _check_tables(_response_part(sec), r.json())
    assert client.post("/optimize").status_code == 200  # body is optional


def test_emergency():
    sec = _section("## 3. `POST /emergency`")
    request = _json_blocks(sec)[0]
    r = client.post("/emergency", json=request)
    assert r.status_code == 200, r.text
    dispatched, no_bus = _json_blocks(_response_part(sec))[:2]
    _compare(dispatched, r.json())
    _check_tables(_response_part(sec), r.json())

    data.reset_live_state()
    for b in data.buses():
        if b["status"] == "spare":
            data.update_bus(b["busId"], status="active")
    r = client.post("/emergency", json=request)
    body = r.json()
    assert body["status"] == "NO_BUS_AVAILABLE"
    for k, v in no_bus.items():
        if k != "timeline":
            assert body[k] == v, k
    _compare(no_bus["timeline"], body["timeline"])

    assert client.post("/emergency/reset").json() == {"status": "reset"}


def test_copilot():
    sec = _section("## 4. `POST /copilot`")
    request = _json_blocks(sec)[0]
    r = client.post("/copilot", json=request)
    assert r.status_code == 200, r.text
    _compare(_json_blocks(_response_part(sec))[0], r.json())
    table = _response_part(sec).split("**Intents**")[1].split("|----------------------|")[-1]
    _check_tables(table, r.json())


def test_dashboard():
    sec = _section("## 5. `GET /dashboard`")
    r = client.get("/dashboard")
    assert r.status_code == 200
    _compare(_json_blocks(_response_part(sec))[0], r.json())
    _check_tables(_response_part(sec), r.json())


@pytest.mark.parametrize("call,status,error", [
    (lambda: client.post("/emergency", json={"incidentType": "BREAKDOWN", "busId": "B099", "station": "Airport"}),
     404, "BUS_NOT_FOUND"),
    (lambda: client.post("/emergency", json={"incidentType": "DRIVER_SICK", "driverId": "D099", "station": "Airport"}),
     404, "DRIVER_NOT_FOUND"),
    (lambda: client.post("/emergency", json={"incidentType": "BREAKDOWN", "busId": "B021", "station": "Mars"}),
     404, "STATION_NOT_FOUND"),
    (lambda: client.post("/emergency", json={"incidentType": "BREAKDOWN", "busId": "B021", "station": "Airport",
                                             "time": "9am"}), 400, "INVALID_TIME"),
    (lambda: client.post("/emergency", json={"incidentType": "BREAKDOWN", "busId": "B021", "station": "Airport",
                                             "time": "25:99"}), 400, "INVALID_TIME"),
    (lambda: client.post("/optimize", json={"candidates": [{
        "startStation": "Airport", "endStation": "University", "headwayMin": 30,
        "serviceStart": "10:00", "serviceEnd": "25:00", "tripDurationMin": 15}]}), 400, "INVALID_REQUEST"),
    (lambda: client.post("/emergency", json={"incidentType": "ROAD_CLOSURE", "station": "Airport"}),
     501, "NOT_IMPLEMENTED"),
    (lambda: client.get("/dashboard", params={"date": "tomorrow"}), 400, "INVALID_DATE"),
    (lambda: client.post("/copilot", json={}), 400, "INVALID_REQUEST"),
])
def test_errors(call, status, error):
    r = call()
    assert r.status_code == status
    assert r.json()["error"] == error and r.json()["message"]


def test_invalid_time_leaves_bus_pool_alone():
    client.post("/emergency", json={"incidentType": "BREAKDOWN", "busId": "B021", "station": "Airport", "time": "25:99"})
    assert next(b for b in data.buses() if b["busId"] == "B021")["status"] == "active"


def test_bus_out_of_service():
    body = {"incidentType": "BREAKDOWN", "busId": "B021", "station": "Airport"}
    client.post("/emergency", json=body)
    r = client.post("/emergency", json=body)
    assert r.status_code == 409 and r.json()["error"] == "BUS_OUT_OF_SERVICE"


def test_cors_for_frontend():
    r = client.options("/dashboard", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_openapi_docs_render():
    assert client.get("/openapi.json").status_code == 200
