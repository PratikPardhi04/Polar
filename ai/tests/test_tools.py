import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from fastapi.testclient import TestClient

import main as ai_main
from tools import CALL_LOG, TOOLS, ToolClient, call_tool


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def test_read_tool_calls_rest_with_token():
    seen = {}

    def handler(request: httpx.Request):
        seen["path"] = request.url.path
        seen["query"] = str(request.url.query)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=[])

    tc = ToolClient(token="user-tok", client=_mock_client(handler))
    assert tc.get_inventory(low_stock=True) == []
    assert seen["path"] == "/api/v1/inventory"
    assert "low_stock" in seen["query"] and seen["auth"] == "Bearer user-tok"
    assert CALL_LOG[-1] == {**CALL_LOG[-1], "tool": "get_inventory", "writes": False}


def test_write_tools_post_drafts_only():
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(201, json={"id": "d1", "status": "DRAFT"})

    tc = ToolClient(token="t", client=_mock_client(handler))
    tc.create_alert(message="storm coming", target_role="LOGISTICS_OFFICER")
    tc.create_work_order(asset_id="a1", problem="rattle")
    tc.create_plan_draft(title="Hold convoy", kind="LOGISTICS", body={"hold": True})
    paths = [c[1] for c in calls]
    assert paths == ["/api/v1/notifications", "/api/v1/work-orders", "/api/v1/plan-drafts"]
    assert all(c[0] == "POST" for c in calls)
    assert "[AI draft" in calls[0][2]["message"] and "[AI-DRAFT" in calls[1][2]["problem"]
    assert calls[2][2]["body"] == {"hold": True}
    assert all(e["writes"] for e in CALL_LOG[-3:])


def test_unknown_tool_rejected():
    try:
        call_tool(ToolClient(token="t"), "drop_database", {})
        raise AssertionError("should have raised")
    except ValueError:
        pass


def test_ai_service_endpoints():
    c = TestClient(ai_main.app)
    assert c.get("/health").status_code == 200
    assert len(c.get("/ai/tools").json()) == len(TOOLS) == 15
    assert c.post("/ai/call", json={"tool": "nope", "args": {}}).status_code == 400
