import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import pytest
from fastapi.testclient import TestClient

import main as ai_main
from agents import APPROVAL_LINE, classify_intent, run_question, validate_node
from tools import CALL_LOG, ToolClient


def _mock_client():
    def handler(request: httpx.Request):
        path = request.url.path
        if path == "/api/v1/shipments":
            return httpx.Response(200, json=[
                {"id": "SHP-1", "origin": "Cape Town", "destination": "Bharati", "status": "IN_TRANSIT", "current_location": "Southern Ocean"},
                {"id": "SHP-2", "origin": "Goa", "destination": "Bharati", "status": "DELAYED", "current_location": "Mumbai"},
            ])
        if path == "/api/v1/field-missions":
            return httpx.Response(200, json=[{"id": "FM-001", "objective": "ice-core", "status": "ACTIVE"}])
        if path == "/api/v1/weather/BHARATI":
            return httpx.Response(200, json={"condition": "CLEAR", "temp_c": -20.0, "wind_kph": 25.0})
        if path == "/api/v1/ai/inventory-forecast":
            return httpx.Response(200, json={"items": [
                {"item_id": "i1", "name": "Diesel", "days_until_stockout": 4.0, "suggested_reorder_qty": 120.0},
                {"item_id": "i2", "name": "Rice", "days_until_stockout": 20.0, "suggested_reorder_qty": 30.0},
            ]})
        if path == "/api/v1/inventory":
            return httpx.Response(200, json=[])
        if path == "/api/v1/incidents":
            return httpx.Response(200, json=[{"id": "inc-9", "incident_type": "MISSING_PERSON", "last_location": "WP-2", "status": "OPEN"}])
        if path == "/api/v1/incidents/inc-9/resources":
            return httpx.Response(200, json={"personnel": [{"full_name": "Standby Op"}], "vehicles": [{"id": "v1", "registration_number": "R-1"}]})
        if path == "/api/v1/plan-drafts" and request.method == "POST":
            return httpx.Response(201, json={"id": "p-draft-1", "status": "DRAFT"})
        if path == "/api/v1/ai/situation-report/generate" and request.method == "POST":
            return httpx.Response(201, json={"id": "sr-1", "status": "DRAFT"})
        return httpx.Response(404, json={"detail": f"mock has no {path}"})

    return ToolClient(token="t", client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test"))


def test_logistics_agent_flags_delayed_cargo():
    out = run_question("Which cargo can affect tomorrow's Bharati mission?", _mock_client())
    assert out["intent"] == "logistics"
    assert "SHP-1" in out["answer"] and "FM-001" in out["answer"]
    assert out["needs_approval"] is True and out["plan_draft_id"] == "p-draft-1"


def test_inventory_agent_ranks_stockout_first():
    out = run_question("Which critical items will run out first?", _mock_client())
    assert out["intent"] == "inventory"
    assert out["answer"].index("Diesel") < out["answer"].index("Rice")
    assert out["plan_draft_id"] == "p-draft-1"


def test_emergency_agent_requires_human_approval():
    out = run_question("What resources can respond to this incident?", _mock_client())
    assert out["intent"] == "emergency"
    assert "Human approval required" in out["answer"]
    assert "Standby Op" in out["answer"] and out["needs_approval"] is True


def test_situation_report_agent_drafts_never_publishes():
    out = run_question("Draft the daily situation report for EXP-46ISEA-2026", _mock_client())
    assert out["intent"] == "report"
    assert out["needs_approval"] is True and out["situation_report_id"] == "sr-1"
    assert "DRAFT" in out["answer"] and "publish" in out["answer"].lower()


def test_validator_blocks_high_consequence_execution():
    state = {"answer": "I will dispatch the rescue team now", "action": None}
    assert validate_node(state)["needs_approval"] is True
    assert classify_intent("rescue the missing team") == "emergency"
    assert classify_intent("fuel running out") == "inventory"
    assert classify_intent("cargo for tomorrow") == "logistics"
    assert classify_intent("draft the daily situation report") == "report"


def test_ask_endpoint_monkeypatched(monkeypatch):
    client = _mock_client()
    monkeypatch.setattr(ai_main, "ToolClient", lambda token="": client)
    c = TestClient(ai_main.app)
    r = c.post("/ai/ask", json={"question": "Which cargo can affect tomorrow's Bharati mission?", "backend_token": "x"})
    assert r.status_code == 200, r.text
    assert r.json()["plan_draft_id"] == "p-draft-1"
    assert len(c.get("/ai/tools").json()) == 15
