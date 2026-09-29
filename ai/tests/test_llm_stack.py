"""Unit tests for the shared LLM stack (A.1–A.5). No GROQ_API_KEY, no network."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from pydantic import BaseModel

import main as ai_main
from app import graph as G
from app import tool_guard as TG


class _Msg:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


class _FakeBound:
    def __init__(self, fake, tools):
        self.fake = fake
        self.fake.bound_with = tools
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        script = self.fake.scripts[min(self.calls - 1, len(self.fake.scripts) - 1)]
        return _Msg(script)


class _FakeStructured:
    def __init__(self, fake, schema, method):
        self.fake = fake
        self.schema = schema
        self.method = method

    def invoke(self, prompt, **kwargs):
        assert self.method == "function_calling", "must use function_calling, never strict mode"
        return {"parsed": self.fake.parsed, "raw": {"echo": True}}


class FakeModel:
    """Stand-in for ChatGroq. scripts: list of tool_call lists per invoke."""

    def __init__(self, scripts=None, parsed=None):
        self.scripts = scripts if scripts is not None else [[{"name": "get_inventory", "args": {}}]]
        self.parsed = parsed
        self.bound_with = None

    def bind_tools(self, tools, tool_choice="auto"):
        self.tool_choice = tool_choice
        return _FakeBound(self, tools)

    def with_structured_output(self, schema, method=None, include_raw=False):
        return _FakeStructured(self, schema, method)


class _Finding(BaseModel):
    summary: str
    items: list[str] = []


def test_model_factory_pinned(monkeypatch):
    from app import llm as LLM

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(LLM.settings, "GROQ_API_KEY", "")
    try:
        LLM.get_model()
        raise AssertionError("should refuse without a key")
    except RuntimeError as exc:
        assert "GROQ_API_KEY" in str(exc)
    monkeypatch.setattr(LLM.settings, "GROQ_API_KEY", "dummy")
    m = LLM.get_model()
    assert m.model_name == "openai/gpt-oss-120b"


def test_structured_helper_strict_mode_never_used():
    from app import structured as ST

    fake = FakeModel(parsed=_Finding(summary="ok", items=["Diesel"]))
    out = ST.structured_call(fake, _Finding, "prompt")  # type: ignore[arg-type]
    assert out.summary == "ok"

    fake_none = FakeModel(parsed=None)
    try:
        ST.structured_call(fake_none, _Finding, "prompt")  # type: ignore[arg-type]
        raise AssertionError("should raise on unparsed output")
    except ValueError as exc:
        assert "_Finding" in str(exc)


def test_tool_guard_retries_then_refuses_to_guess():
    fake_ok = FakeModel(scripts=[[ {"name": "get_inventory", "args": {}} ]])
    resp = TG.invoke_with_required_tools(fake_ok, ["get_inventory"], [("user", "q")])
    assert resp.tool_calls[0]["name"] == "get_inventory"

    fake_retry = FakeModel(scripts=[[], [{"name": "get_inventory", "args": {}}]])
    resp = TG.invoke_with_required_tools(fake_retry, ["get_inventory"], [("user", "q")])
    assert resp.tool_calls[0]["name"] == "get_inventory"

    fake_silent = FakeModel(scripts=[[], []])
    try:
        TG.invoke_with_required_tools(fake_silent, ["get_inventory"], [("user", "q")])
        raise AssertionError("should raise after retries")
    except RuntimeError as exc:
        assert "insufficient data" in str(exc)


def test_backend_tools_hit_rest_not_db(monkeypatch):
    import httpx

    from app import backend_tools as BT

    seen = {}

    def fake_get(url, params=None, headers=None, timeout=10.0):
        seen.update(url=url, params=params, auth=headers.get("Authorization"))
        class R:
            def raise_for_status(self): ...

            def json(self):
                return [{"name": "Diesel", "quantity": 5, "minimum_stock": 10}]

        return R()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(BT.settings, "BACKEND_URL", "http://test-backend")
    monkeypatch.setattr(BT.settings, "AI_SERVICE_TOKEN", "svc-tok")
    out = BT.get_inventory.func("Fuel") if hasattr(BT.get_inventory, "func") else BT.get_inventory.invoke({"category": "Fuel"})
    assert out[0]["name"] == "Diesel"
    assert seen["url"] == "http://test-backend/api/v1/inventory" and seen["auth"] == "Bearer svc-tok"
    assert len(BT.TOOL_MAP) == 11


def _graph_fake():
    return FakeModel(
        scripts=[[ {"name": "get_transport_schedule", "args": {}} ]],
        parsed={"summary": "s", "key_points": ["k"], "proposed_action": "none", "high_consequence": False},
    )


def test_graph_logistics_run_end_to_end(monkeypatch):
    import httpx

    from app import backend_tools as BT

    def fake_get(url, params=None, headers=None, timeout=10.0):
        class R:
            def raise_for_status(self): ...

            def json(self):
                return []

        return R()

    monkeypatch.setattr(httpx, "get", fake_get)
    out = G.run_turn("which cargo is moving?", thread_id="ut-log", model=_graph_fake())
    assert out["intent"] == "logistics"
    assert out["requires_approval"] is False
    assert "logistics" in out["audit_note"] and "not required" in out["audit_note"]


def test_graph_blocks_dispatch_and_pauses_for_approval(monkeypatch):
    import httpx

    from app import backend_tools as BT

    def fake_get(url, params=None, headers=None, timeout=10.0):
        class R:
            def raise_for_status(self): ...

            def json(self):
                return []

        return R()

    monkeypatch.setattr(httpx, "get", fake_get)
    fake = FakeModel(
        scripts=[[ {"name": "get_active_incidents", "args": {}} ]],
        parsed={"summary": "s", "key_points": [], "proposed_action": "dispatch the rescue team now", "high_consequence": True},
    )
    out = G.run_turn("rescue the missing team", thread_id="ut-emg", model=fake)
    assert out["intent"] == "emergency"
    assert out["requires_approval"] is True
    assert out["approved"] is False
    assert "PAUSED" in out["gate_note"]
    marked = G.mark_approved("ut-emg", approver="test-lead")
    assert marked.get("approved") is True


def test_phase9_slots_are_explicit_stubs():
    out = G.run_turn("audit findings", thread_id="ut-stub", model=FakeModel(scripts=[[]]))
    assert out["intent"] == "inventory_audit"
    assert "Phase 9" in (out["draft_output"] or {}).get("summary", "")


def test_ask_llm_endpoint_behaviour(monkeypatch):
    from app import settings as S

    monkeypatch.setattr(S.settings, "GROQ_API_KEY", "")
    c = TestClient(ai_main.app)
    r = c.post("/ai/ask-llm", json={"question": "hi"})
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["detail"]
