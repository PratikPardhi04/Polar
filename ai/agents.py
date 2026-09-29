"""POLARIS agents + LangGraph orchestrator (Phase 6.3).

Graph: START → classify → retrieve_context → route →
  Logistics | Inventory | Emergency (6.1 tools only) →
  validate → gate → action → audit → END.

- The validator blocks high-consequence language from executing: agents may
  only propose DRAFT plans; execution (APPROVE) is a human backend call.
- The Emergency agent always states "Human approval required" and never
  dispatches on its own.
- Deterministic keyword routing — no LLM key required for the prototype.
"""

from datetime import datetime, timezone
from typing import TypedDict
import re

from langgraph.graph import END, START, StateGraph

from tools import CALL_LOG, ToolClient
HIGH_CONSEQUENCE = ("dispatch", "rescue", "cancel", "deploy", "override", "evacuat", "launch")
IN_TRANSIT = {"DISPATCHED", "IN_TRANSIT", "AT_GATEWAY", "LOADED", "ARRIVED_ANTARCTICA", "RECEIVED_AT_STATION"}
APPROVAL_LINE = "Human approval required — the AI proposes, a human APPROVEs via POST /api/v1/plan-drafts/{id}/decide."


class AIState(TypedDict, total=False):
    question: str
    client: ToolClient
    intent: str
    context: dict
    answer: str
    action: dict | None
    needs_approval: bool
    plan_draft_id: str | None
    situation_report_id: str | None
    validator_note: str
    audit_note: str


def classify_intent(question: str) -> str:
    q = (question or "").lower()
    if any(k in q for k in ("situation report", "sitrep", "daily report")):
        return "report"
    if any(k in q for k in ("incident", "sos", "rescue", "respond", "emergency", "medical", "missing")):
        return "emergency"
    if any(k in q for k in ("stock", "inventory", "run out", "reorder", "forecast", "fuel", "consume")):
        return "inventory"
    return "logistics"


def classify_node(state: AIState) -> dict:
    return {"intent": classify_intent(state.get("question", ""))}


def context_node(state: AIState) -> dict:
    client: ToolClient = state["client"]
    intent = state.get("intent", "logistics")
    ctx: dict = {}
    try:
        if intent == "logistics":
            ctx["schedule"] = client.get_transport_schedule()
            ctx["missions"] = client.get_missions()
            ctx["weather"] = client.get_weather_snapshot("BHARATI")
        elif intent == "inventory":
            ctx["forecast"] = client.get_inventory_forecast(only_at_risk=True)
            ctx["low_stock"] = client.get_inventory(low_stock=True)
        elif intent == "report":
            ctx["report_hint"] = "backend composer gathers the day slice on generate"
        else:
            ctx["incidents"] = client.get_active_incidents()
    except Exception as exc:
        ctx["error"] = f"context retrieval failed: {exc}"
    return {"context": ctx}


def logistics_agent(state: AIState) -> dict:
    ctx = state.get("context", {})
    if "error" in ctx:
        return {"answer": f"Could not reach operations data: {ctx['error']}", "action": None}
    moving = [s for s in ctx.get("schedule", []) if s.get("status") in IN_TRANSIT]
    delayed = [s for s in ctx.get("schedule", []) if s.get("status") == "DELAYED"]
    missions = [m for m in ctx.get("missions", []) if m.get("status") in ("ACTIVE", "DEPLOYED", "APPROVED", "PLANNED")]
    lines = [f"{s['id']} [{s['status']}] {s['route']} @ {s['location']}" for s in moving]
    mlines = [f"{m['id']} [{m.get('status')}] {m.get('objective', '')}" for m in missions]
    wx = ctx.get("weather", {})
    answer = (
        f"Cargo that can affect Bharati missions: {len(moving)} shipment(s) in transit. "
        + ("; ".join(lines) if lines else "none moving. ")
        + f"Active/planned missions ({len(missions)}): " + ("; ".join(mlines) if mlines else "none. ")
        + f"Bharati weather: {wx.get('condition', '?')} {wx.get('temp_c', '?')}C wind {wx.get('wind_kph', '?')} kph."
    )
    action = None
    if delayed:
        action = {"tool": "create_plan_draft", "args": {"title": f"Hold convoy — {delayed[0]['id']} delayed", "kind": "LOGISTICS", "body": {"delayed": [d["id"] for d in delayed]}}}
    return {"answer": answer, "action": action}


def inventory_agent(state: AIState) -> dict:
    ctx = state.get("context", {})
    if "error" in ctx:
        return {"answer": f"Could not reach inventory data: {ctx['error']}", "action": None}
    items = (ctx.get("forecast", {}) or {}).get("items", [])
    if not items:
        return {"answer": "No items are forecast at risk of stockout in the window.", "action": None}
    ranked = "; ".join(f"{i['name']} ({i['days_until_stockout']} days left, reorder {i['suggested_reorder_qty']})" for i in items[:5])
    top = items[0]
    return {
        "answer": f"Critical items running out first: {ranked}.",
        "action": {"tool": "create_plan_draft", "args": {"title": f"Reorder {top['name']}", "kind": "INVENTORY", "body": {"item_id": top["item_id"], "qty": top["suggested_reorder_qty"]}}},
    }


def emergency_agent(state: AIState) -> dict:
    ctx = state.get("context", {})
    client: ToolClient = state["client"]
    if "error" in ctx:
        return {"answer": f"Could not reach incident data: {ctx['error']}. {APPROVAL_LINE}", "action": None}
    incidents = ctx.get("incidents", [])
    if not incidents:
        return {"answer": f"No active incidents. {APPROVAL_LINE}", "action": None}
    parts = []
    for inc in incidents[:3]:
        try:
            res = client.get_incident_resources(inc["id"])
            crew = ", ".join(p["full_name"] for p in res.get("personnel", [])[:4]) or "none available"
            veh = ", ".join(v["registration_number"] or v["id"] for v in res.get("vehicles", [])[:3]) or "none available"
        except Exception:
            crew, veh = "unknown", "unknown"
        parts.append(f"{inc['id']} [{inc.get('incident_type')}] @ {inc.get('last_location', '?')}: crew [{crew}], vehicles [{veh}]")
    return {
        "answer": "Response options (recommendations only — nothing dispatched): " + " | ".join(parts) + f". {APPROVAL_LINE}",
        "action": {"tool": "create_plan_draft", "args": {"title": f"Respond to {incidents[0]['id']}", "kind": "EMERGENCY", "body": {"incident_id": incidents[0]["id"]}}},
    }


def agent_router(state: AIState) -> str:
    return {"emergency": "emergency", "inventory": "inventory", "report": "report"}.get(state.get("intent", "logistics"), "logistics")


def situation_agent(state: AIState) -> dict:
    """Fourth agent: drafts the Daily Situation Report via the backend composer."""
    q = state.get("question", "")
    exp = re.search(r"EXP-[A-Z0-9\-]+", q.upper())
    expedition_id = exp.group(0) if exp else "EXP-46ISEA-2026"
    day = re.search(r"\d{4}-\d{2}-\d{2}", q)
    report_date = day.group(0) if day else datetime.now(timezone.utc).date().isoformat()
    return {
        "answer": (
            f"Daily Situation Report draft for {expedition_id} ({report_date}): "
            "Personnel, Cargo, Inventory, Field Operations, Incidents, Risks/Recommendations "
            "composed from live backend data and saved as DRAFT. A Station/Expedition Leader must publish it — never auto-published."
        ),
        "action": {"tool": "generate_situation_report", "args": {"expedition_id": expedition_id, "date": report_date}},
    }


def validate_node(state: AIState) -> dict:
    text = f"{state.get('answer', '')} {state.get('action') or ''}".lower()
    hot = [w for w in HIGH_CONSEQUENCE if w in text]
    action = state.get("action")
    if action is not None:
        return {"needs_approval": True, "validator_note": f"draft-only action proposed ({action['tool']}); execution requires human APPROVE" + (f"; high-consequence terms present: {hot}" if hot else "")}
    if hot:
        safe = state.get("answer", "") + f" {APPROVAL_LINE}"
        return {"needs_approval": True, "answer": safe, "validator_note": f"blocked autonomous execution; terms: {hot}"}
    return {"needs_approval": False, "validator_note": "answer only, no action"}


def gate_route(state: AIState) -> str:
    return "act" if state.get("needs_approval") else "audit"


def action_node(state: AIState) -> dict:
    """Executes ONLY draft creation (audited backend-side). Never dispatches."""
    action = state.get("action")
    if not action:
        return {"plan_draft_id": None, "situation_report_id": None}
    client: ToolClient = state["client"]
    tool, args = action["tool"], action["args"]
    if tool == "create_plan_draft":
        out = client.create_plan_draft(title=args["title"], kind=args.get("kind", "GENERAL"), body=args.get("body"))
        return {"plan_draft_id": out.get("id")}
    if tool == "generate_situation_report":
        out = client.generate_situation_report(expedition_id=args["expedition_id"], date=args["date"])
        return {"situation_report_id": out.get("id")}
    if tool == "create_alert":
        out = client.create_alert(message=args["message"], target_role=args.get("target_role", "EMERGENCY_COORDINATOR"))
    elif tool == "create_work_order":
        out = client.create_work_order(asset_id=args["asset_id"], problem=args["problem"], priority=args.get("priority", "MEDIUM"))
    else:
        return {"plan_draft_id": None, "situation_report_id": None, "validator_note": f"validator refused unknown action tool {tool}"}
    return {"plan_draft_id": out.get("id")}


def audit_node(state: AIState) -> dict:
    note = f"intent={state.get('intent')} approval={'required' if state.get('needs_approval') else 'not required'} draft={state.get('plan_draft_id')}"
    CALL_LOG.append({"tool": "ai_run_audit", "args": {"question": state.get("question", "")[:120]}, "writes": False, "at": note})
    return {"audit_note": note}


def build_graph():
    g = StateGraph(AIState)
    g.add_node("classify", classify_node)
    g.add_node("context", context_node)
    g.add_node("logistics", logistics_agent)
    g.add_node("inventory", inventory_agent)
    g.add_node("emergency", emergency_agent)
    g.add_node("report", situation_agent)
    g.add_node("validate", validate_node)
    g.add_node("act", action_node)
    g.add_node("audit", audit_node)
    g.add_edge(START, "classify")
    g.add_edge("classify", "context")
    g.add_conditional_edges("context", agent_router, {"logistics": "logistics", "inventory": "inventory", "emergency": "emergency", "report": "report"})
    g.add_edge("logistics", "validate")
    g.add_edge("inventory", "validate")
    g.add_edge("emergency", "validate")
    g.add_edge("report", "validate")
    g.add_conditional_edges("validate", gate_route, {"act": "act", "audit": "audit"})
    g.add_edge("act", "audit")
    g.add_edge("audit", END)
    return g.compile()


GRAPH = build_graph()


def run_question(question: str, client: ToolClient) -> dict:
    out = GRAPH.invoke({"question": question, "client": client})
    return {
        "answer": out.get("answer", ""),
        "intent": out.get("intent", ""),
        "needs_approval": out.get("needs_approval", False),
        "plan_draft_id": out.get("plan_draft_id"),
        "situation_report_id": out.get("situation_report_id"),
        "validator_note": out.get("validator_note", ""),
        "audit_note": out.get("audit_note", ""),
    }
