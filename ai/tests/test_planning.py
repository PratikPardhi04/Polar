import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from fastapi.testclient import TestClient

import main as ai_main
from planning import generate_plan
from tools import ToolClient

FORECAST = {"items": [
    {"item_id": "f1", "name": "Rice", "category": "Food", "on_hand": 40.0, "available": 40.0, "avg_daily_use": 10.0, "days_until_stockout": 4.0, "at_risk": True},
    {"item_id": "f2", "name": "Diesel", "category": "Fuel", "on_hand": 500.0, "available": 500.0, "avg_daily_use": 5.0, "days_until_stockout": 100.0, "at_risk": False},
]}
INVENTORY = [
    {"id": "f1", "name": "Rice", "unit": "kg", "minimum_stock": 100},
    {"id": "f2", "name": "Diesel", "unit": "L", "minimum_stock": 400},
]


def _mock_client(captured):
    def handler(request: httpx.Request):
        path = request.url.path
        if path == "/api/v1/ai/inventory-forecast":
            return httpx.Response(200, json=FORECAST)
        if path == "/api/v1/inventory":
            return httpx.Response(200, json=INVENTORY)
        if path == "/api/v1/plan-drafts" and request.method == "POST":
            import json as j

            captured["draft"] = j.loads(request.content)
            return httpx.Response(201, json={"id": "plan-1", "status": "DRAFT"})
        return httpx.Response(404, json={"detail": path})

    return ToolClient(token="t", client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test"))


def test_food_plan_math_and_draft():
    captured: dict = {}
    out = generate_plan(_mock_client(captured), "FOOD", 14)
    assert [l["name"] for l in out["lines"]] == ["Rice"]  # Diesel filtered out
    rice = out["lines"][0]
    assert rice["status"] == "ORDER NOW" and rice["suggested_qty"] == 170.0  # 10*14-40 + 10*7
    assert out["plan_draft_id"] == "plan-1"
    assert captured["draft"]["kind"] == "INVENTORY" and "FOOD" in captured["draft"]["title"].upper()
    assert "APPROVE" in out["approval_note"]


def test_supplies_and_full_kinds():
    captured: dict = {}
    out = generate_plan(_mock_client(captured), "SUPPLIES", 14)
    assert [l["name"] for l in out["lines"]] == ["Diesel"]
    assert out["lines"][0]["status"] == "OK" and out["lines"][0]["suggested_qty"] == 0.0
    out = generate_plan(_mock_client({}), "FULL", 3)
    assert len(out["lines"]) == 2 and out["lines"][0]["name"] == "Rice"  # urgency first
    try:
        generate_plan(_mock_client({}), "NOPE", 14)
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_plan_endpoint_validation():
    c = TestClient(ai_main.app)
    assert c.post("/ai/plan/generate", json={"kind": "NOPE"}).status_code == 400
