"""LLM orchestrator graph (addendum A.5).

START → classify_intent → retrieve_context →
  {logistics | inventory | emergency | inventory_audit | usage_planning} →
  risk_validator → (conditional) human_approval_gate → audit_log → END.

Rules:
- Agent nodes use the shared model factory (tests inject fakes via override),
  invoke_with_required_tools() for every tool-dependent step, and
  structured_call() for draft_output. Raw model text is never saved.
- risk_validator is a deterministic Python check, never an LLM call.
- The graph NEVER writes to the backend: draft_output is data. A human turns
  it into a real DRAFT via POST /api/v1/plan-drafts (audited there).
- MemorySaver checkpoint keeps per-thread state so a paused-for-approval run
  can be inspected/resumed; approval itself is the backend APPROVE action.
"""

from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from .backend_tools import TOOL_MAP
from .llm import get_model
from .structured import structured_call
from .tool_guard import invoke_with_required_tools


class AgentState(TypedDict, total=False):
    messages: list
    question: str
    intent: str | None
    tool_results: dict
    draft_output: dict | None
    requires_approval: bool
    approved: bool
    gate_note: str
    audit_note: str


# Test/ops override for the model (unit tests inject fakes here). Never part of
# checkpointed state — checkpoint serializers (msgpack) cannot serialize client
# objects, real ChatGroq included.
_MODEL_OVERRIDE = None


def _model(state: AgentState):
    _ = state
    return _MODEL_OVERRIDE or get_model()


class DraftOutput(BaseModel):
    summary: str
    key_points: list[str] = []
    proposed_action: str = "none"
    high_consequence: bool = False


HIGH_CONSEQUENCE_VERBS = ("dispatch", "reserve", "cancel", "publish", "approve", "deploy", "override", "evacuat", "launch")

INSUFFICIENT = "insufficient data, human should check manually"


def _model(state: AgentState):
    _ = state
    return _MODEL_OVERRIDE or get_model()


def classify_intent(state: AgentState) -> dict:
    q = (state.get("question") or "").lower()
    if any(k in q for k in ("audit", "finding", "findings", "compliance gap")):
        return {"intent": "inventory_audit"}
    if any(k in q for k in ("usage", "consumption plan", "plan consumption", "ration")):
        return {"intent": "usage_planning"}
    if any(k in q for k in ("incident", "sos", "rescue", "respond", "emergency", "medical", "missing")):
        return {"intent": "emergency"}
    if any(k in q for k in ("stock", "inventory", "run out", "reorder", "forecast", "fuel", "consume")):
        return {"intent": "inventory"}
    return {"intent": "logistics"}


def retrieve_context(state: AgentState) -> dict:
    return {"tool_results": {}, "messages": [{"role": "user", "content": state.get("question", "")}]}


def _run_agent(state: AgentState, system: str, tools: list) -> dict:
    model = _model(state)
    messages = [("system", system), ("user", state.get("question", ""))]
    try:
        response = invoke_with_required_tools(model, tools, messages)
    except RuntimeError:
        return {
            "tool_results": {},
            "draft_output": {"summary": INSUFFICIENT, "key_points": [], "proposed_action": "none", "high_consequence": False},
        }
    results = {}
    for call in getattr(response, "tool_calls", None) or []:
        name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
        args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})
        if name in TOOL_MAP:
            try:
                results[name] = TOOL_MAP[name].invoke(args or {})
            except Exception as exc:
                results[name] = {"error": str(exc)[:300]}
    try:
        draft = structured_call(
            model, DraftOutput,
            [("system", "Summarize the tool results for the operator. Propose at most one next action as plain text; you execute nothing yourself."), ("user", f"Question: {state.get('question', '')}\nTool results: {results}")],
        )
        draft_dict = draft.model_dump() if hasattr(draft, "model_dump") else dict(draft)
    except ValueError:
        draft_dict = {"summary": INSUFFICIENT, "key_points": [], "proposed_action": "none", "high_consequence": False}
    return {"tool_results": results, "draft_output": draft_dict}


def logistics_agent(state: AgentState) -> dict:
    return _run_agent(state, "You are the POLARIS logistics analyst. Always call a cargo/mission/weather tool before answering.", [TOOL_MAP["get_transport_schedule"], TOOL_MAP["get_missions"], TOOL_MAP["get_weather_snapshot"]])


def inventory_agent(state: AgentState) -> dict:
    return _run_agent(state, "You are the POLARIS inventory analyst. Always call an inventory tool before answering.", [TOOL_MAP["get_inventory"], TOOL_MAP["get_inventory_forecast"]])


def emergency_agent(state: AgentState) -> dict:
    return _run_agent(state, "You are the POLARIS emergency analyst. Always call an incident tool before answering. Recommend only; state that human approval is required.", [TOOL_MAP["get_active_incidents"], TOOL_MAP["get_incident_resources"]])


def inventory_audit_agent(state: AgentState) -> dict:
    """Phase 9 slot — not wired yet. Explicit pending message, never a guess."""
    return {
        "tool_results": {},
        "draft_output": {"summary": "Inventory Audit agent lands in Phase 9 — not yet wired.", "key_points": [], "proposed_action": "none", "high_consequence": False},
    }


def usage_planning_agent(state: AgentState) -> dict:
    """Phase 9 slot — not wired yet. Explicit pending message, never a guess."""
    return {
        "tool_results": {},
        "draft_output": {"summary": "Usage Planning agent lands in Phase 9 — not yet wired.", "key_points": [], "proposed_action": "none", "high_consequence": False},
    }


def route_intent(state: AgentState) -> str:
    return state.get("intent") or "logistics"


def risk_validator(state: AgentState) -> dict:
    """Deterministic Python gate — never an LLM call."""
    draft = state.get("draft_output") or {}
    text = f"{draft.get('summary', '')} {' '.join(draft.get('key_points', []))} {draft.get('proposed_action', '')}".lower()
    hot = [w for w in HIGH_CONSEQUENCE_VERBS if w in text]
    needs = bool(draft.get("high_consequence")) or bool(hot) or draft.get("proposed_action", "none").strip().lower() != "none"
    note = "draft-only; execution requires human APPROVE" + (f"; high-consequence terms: {hot}" if hot else "")
    return {"requires_approval": needs, "gate_note": note if needs else "answer only, no action"}


def human_approval_gate(state: AgentState) -> dict:
    if state.get("requires_approval") and not state.get("approved"):
        return {"gate_note": (state.get("gate_note") or "") + " — PAUSED for human approval (checkpoint keeps this run resumable)"}
    return {"approved": True, "gate_note": "approved or no approval needed — see backend audit on execution"}


def gate_route(state: AgentState) -> str:
    if state.get("requires_approval") and not state.get("approved"):
        return "pending"
    return "audit"


def pending_note(state: AgentState) -> dict:
    return {"audit_note": f"pending approval kept in checkpoint thread; draft={state.get('draft_output') or {}} "[:500]}


def audit_log(state: AgentState) -> dict:
    try:
        from tools import CALL_LOG

        CALL_LOG.append({"tool": "llm_run_audit", "args": {"intent": state.get("intent"), "requires_approval": state.get("requires_approval")}, "writes": False, "at": "llm-graph"})
    except Exception:
        pass
    return {"audit_note": f"intent={state.get('intent')} approval={'required' if state.get('requires_approval') else 'not required'}"}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("classify_intent", classify_intent)
    g.add_node("retrieve_context", retrieve_context)
    g.add_node("logistics_agent", logistics_agent)
    g.add_node("inventory_agent", inventory_agent)
    g.add_node("emergency_agent", emergency_agent)
    g.add_node("inventory_audit_agent", inventory_audit_agent)
    g.add_node("usage_planning_agent", usage_planning_agent)
    g.add_node("risk_validator", risk_validator)
    g.add_node("human_approval_gate", human_approval_gate)
    g.add_node("pending", pending_note)
    g.add_node("audit_log", audit_log)
    g.add_edge(START, "classify_intent")
    g.add_edge("classify_intent", "retrieve_context")
    g.add_conditional_edges(
        "retrieve_context", route_intent,
        {"logistics": "logistics_agent", "inventory": "inventory_agent", "emergency": "emergency_agent", "inventory_audit": "inventory_audit_agent", "usage_planning": "usage_planning_agent"},
    )
    for agent in ("logistics_agent", "inventory_agent", "emergency_agent", "inventory_audit_agent", "usage_planning_agent"):
        g.add_edge(agent, "risk_validator")
    g.add_edge("risk_validator", "human_approval_gate")
    g.add_conditional_edges("human_approval_gate", gate_route, {"pending": "pending", "audit": "audit_log"})
    g.add_edge("pending", END)
    g.add_edge("audit_log", END)
    return g.compile(checkpointer=MemorySaver())


GRAPH = build_graph()


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def run_turn(question: str, thread_id: str = "demo", model=None, approved: bool = False) -> dict:
    """Run one turn. Returns intent, draft_output, requires_approval and notes."""
    global _MODEL_OVERRIDE
    prev, _MODEL_OVERRIDE = _MODEL_OVERRIDE, model
    try:
        out = GRAPH.invoke({"question": question, "approved": approved}, config=_config(thread_id))
    finally:
        _MODEL_OVERRIDE = prev
    return {
        "intent": out.get("intent"),
        "draft_output": out.get("draft_output"),
        "tool_results": out.get("tool_results", {}),
        "requires_approval": out.get("requires_approval", False),
        "approved": out.get("approved", False),
        "gate_note": out.get("gate_note", ""),
        "audit_note": out.get("audit_note", ""),
        "thread_id": thread_id,
    }


def mark_approved(thread_id: str, approver: str = "human") -> dict:
    """Record a human approval against a paused thread (execution itself stays
    on the backend APPROVE endpoint, audited there)."""
    GRAPH.update_state(_config(thread_id), {"approved": True, "gate_note": f"approved by {approver} — execute via backend"})
    return GRAPH.get_state(_config(thread_id)).values
