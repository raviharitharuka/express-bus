"""Lotse with the Claude API mocked: the Claude path, and every fallback to the keyword rules.

No test here touches the network: services.claude._client is replaced by a fake.
"""

import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from schemas.lotse import LotseRequest
from services import claude, data
from services.lotse import answer_with_rules, ask
from tests.test_contract import client

QUESTION = "Can we launch a new express route tomorrow?"
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def message(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


class FakeClaude:
    """Returns (or raises) one scripted item per messages.create call and records the calls."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("DEMO_DATE", "2026-10-05")
    data.reset_live_state()
    yield
    data.reset_live_state()


def use(monkeypatch, fake: FakeClaude) -> FakeClaude:
    monkeypatch.setattr(claude, "_client", lambda: fake)
    return fake


def rules(question: str = QUESTION):
    return answer_with_rules(LotseRequest(question=question)).model_dump()


# --- Fallback to the keyword rules ------------------------------------------------

def test_missing_key_uses_rules_without_calling_the_api(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(anthropic, "Anthropic", lambda **_: pytest.fail("no client without a key"))
    r = ask(LotseRequest(question=QUESTION))
    assert r.explained_by == "rules" and r.model_dump() == rules()


def test_timeout_during_classification_uses_rules(monkeypatch):
    fake = use(monkeypatch, FakeClaude(anthropic.APITimeoutError(request=REQUEST)))
    r = ask(LotseRequest(question=QUESTION))
    assert r.explained_by == "rules" and r.model_dump() == rules()
    assert len(fake.calls) == 1


def test_api_error_while_explaining_uses_rules(monkeypatch):
    server_error = anthropic.InternalServerError(
        "overloaded", response=httpx2.Response(500, request=REQUEST), body=None)
    fake = use(monkeypatch, FakeClaude(message('{"intent": "launch_route"}'), server_error))
    r = ask(LotseRequest(question=QUESTION))
    assert r.explained_by == "rules" and r.model_dump() == rules()
    assert len(fake.calls) == 2


def test_refusal_uses_rules(monkeypatch):
    use(monkeypatch, FakeClaude(message("", stop_reason="refusal")))
    assert ask(LotseRequest(question=QUESTION)).explained_by == "rules"


def test_unparseable_classification_uses_rules(monkeypatch):
    use(monkeypatch, FakeClaude(message("launch_route")))  # not the JSON the schema asks for
    assert ask(LotseRequest(question=QUESTION)).model_dump() == rules()


def test_fallback_through_the_http_endpoints(monkeypatch):
    use(monkeypatch, FakeClaude(anthropic.APIConnectionError(request=REQUEST),
                                anthropic.APIConnectionError(request=REQUEST)))
    for path in ("/lotse", "/copilot"):
        body = client.post(path, json={"question": QUESTION}).json()
        assert body["explainedBy"] == "rules" and body["intent"] == "launch_route"


# --- The Claude path ----------------------------------------------------------

def test_claude_classifies_runs_the_service_and_explains(monkeypatch):
    fake = use(monkeypatch, FakeClaude(
        message('{"intent": "launch_route"}'),
        message("Yes: E1 and E3 can launch on 2026-10-06 with existing drivers."),
    ))
    r = ask(LotseRequest(question=QUESTION))
    assert r.explained_by == "claude" and r.intent == "launch_route"
    assert r.answer == "Yes: E1 and E3 can launch on 2026-10-06 with existing drivers."
    assert r.data == rules()["data"]  # same service result as the rules path

    classify, explain = fake.calls
    for call in fake.calls:
        assert call["model"] == "claude-opus-5-5" and call["fallbacks"] == "default"
        assert call["betas"] == ["server-side-fallback-2026-07-01"]
    labels = classify["output_config"]["format"]["schema"]["properties"]["intent"]["enum"]
    assert set(labels) == {"launch_route", "idle_drivers", "breakdown", "station_buses", "driver_shortage",
                           "greeting", "unknown"}
    assert explain["system"] == claude.EXPLAIN_SYSTEM
    assert "Never estimate or add figures" in explain["system"]
    sent = explain["messages"][0]["content"]
    assert QUESTION in sent and json.dumps(r.data, ensure_ascii=False, sort_keys=True) in sent


def test_claude_unknown_gives_the_rules_fallback_message(monkeypatch):
    use(monkeypatch, FakeClaude(message('{"intent": "unknown"}')))
    r = ask(LotseRequest(question="What's the weather like?"))
    assert r.intent == "unknown" and r.explained_by == "rules" and "Ask Lotse about" in r.answer


def test_breakdown_explained_by_claude_stays_a_what_if(monkeypatch):
    use(monkeypatch, FakeClaude(message('{"intent": "breakdown"}'), message("D011 would bring B027.")))
    r = ask(LotseRequest(question="What happens if bus B021 breaks down at 09:15?"))
    assert r.explained_by == "claude" and r.data["hypothetical"] is True
    assert next(b for b in data.buses() if b["busId"] == "B021")["status"] == "active"


def test_client_uses_the_key_a_5_second_timeout_and_no_retries(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    c = claude._client()
    assert c.api_key == "sk-test-not-real" and c.timeout == 5.0 and c.max_retries == 0
