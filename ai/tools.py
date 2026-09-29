"""POLARIS AI tools (Phase 6.1).

Ground rules enforced here:
- Tools call the backend REST API with the caller's bearer token (RBAC preserved).
  The LLM never touches the database directly.
- Only create_alert / create_work_order / create_plan_draft may write, and each
  only creates a record awaiting human approval (UNREAD advisory / OPEN work
  order / DRAFT plan). Nothing executes a real-world action.
- Every tool call is logged (in-memory ring + stdlib logging).
"""

import logging
import os
from datetime import datetime, timezone

import httpx

log = logging.getLogger("polaris.ai.tools")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

CALL_LOG: list[dict] = []


def _record(tool: str, args: dict, writes: bool):
    entry = {"tool": tool, "args": args, "writes": writes, "at": datetime.now(timezone.utc).isoformat()}
    CALL_LOG.append(entry)
    if len(CALL_LOG) > 200:
        del CALL_LOG[: len(CALL_LOG) - 200]
    log.info("AI tool call: %s args=%s", tool, args)
    return entry


class ToolClient:
    """Backend REST client. Pass an httpx.Client (e.g. MockTransport) in tests."""

    def __init__(self, backend_url: str = BACKEND_URL, token: str = "", client: httpx.Client | None = None):
        self.backend_url = backend_url.rstrip("/")
        self.token = token
        self._client = client

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _get(self, path: str, params: dict | None = None):
        if self._client is not None:
            r = self._client.get(path, params=params, headers=self._headers())
            r.raise_for_status()
            return r.json()
        with httpx.Client(base_url=self.backend_url, timeout=20.0) as c:
            r = c.get(f"{self.backend_url}{path}", params=params, headers=self._headers())
            r.raise_for_status()
            return r.json()

    def _post(self, path: str, body: dict):
        if self._client is not None:
            r = self._client.post(path, json=body, headers=self._headers())
            r.raise_for_status()
            return r.json()
        with httpx.Client(base_url=self.backend_url, timeout=20.0) as c:
            r = c.post(f"{self.backend_url}{path}", json=body, headers=self._headers())
            r.raise_for_status()
            return r.json()

    # ---- read tools (no writes) ----
    def get_person_status(self, query: str = ""):
        _record("get_person_status", {"query": query}, False)
        return self._get("/api/v1/personnel", params={"q": query} if query else None)

    def get_cargo_status(self, ref: str):
        _record("get_cargo_status", {"ref": ref}, False)
        if ref.upper().startswith("BX-") or ref.upper().startswith("POLARIS:"):
            pid = ref.split("POLARIS:")[-1].strip()
            return self._get(f"/api/v1/packages/{pid}")
        return self._get(f"/api/v1/shipments/{ref}")

    def get_inventory(self, low_stock: bool = False, category: str = ""):
        _record("get_inventory", {"low_stock": low_stock, "category": category}, False)
        params = {}
        if low_stock:
            params["low_stock"] = "true"
        if category:
            params["category"] = category
        return self._get("/api/v1/inventory", params=params or None)

    def get_vehicle_status(self):
        _record("get_vehicle_status", {}, False)
        return self._get("/api/v1/vehicles")

    def get_station_capacity(self):
        _record("get_station_capacity", {}, False)
        stations = self._get("/api/v1/stations")
        expeditions = self._get("/api/v1/expeditions")
        by_station: dict[str, int] = {}
        for e in expeditions:
            sid = e.get("primary_station_id", "?")
            by_station[sid] = by_station.get(sid, 0) + 1
        return {"note": "estimate: expeditions per station (no berth model yet)", "stations": stations, "expeditions_per_station": by_station}

    def get_weather_snapshot(self, station: str):
        _record("get_weather_snapshot", {"station": station}, False)
        return self._get(f"/api/v1/weather/{station}")

    def get_active_incidents(self):
        _record("get_active_incidents", {}, False)
        all_inc = self._get("/api/v1/incidents")
        return [i for i in all_inc if i.get("status") not in ("RESOLVED", "CLOSED")]

    def get_transport_schedule(self):
        _record("get_transport_schedule", {}, False)
        ships = self._get("/api/v1/shipments")
        return [{"id": s["id"], "route": f"{s['origin']} -> {s['destination']}", "status": s["status"], "location": s["current_location"]} for s in ships]

    def get_inventory_forecast(self, only_at_risk: bool = True):
        _record("get_inventory_forecast", {"only_at_risk": only_at_risk}, False)
        return self._get("/api/v1/ai/inventory-forecast", params={"only_at_risk": "true" if only_at_risk else "false"})

    def get_missions(self):
        _record("get_missions", {}, False)
        return self._get("/api/v1/field-missions")

    def get_incident_resources(self, incident_id: str):
        _record("get_incident_resources", {"incident_id": incident_id}, False)
        return self._get(f"/api/v1/incidents/{incident_id}/resources")

    def generate_situation_report(self, expedition_id: str, date: str):
        _record("generate_situation_report", {"expedition_id": expedition_id, "date": date}, True)
        return self._post("/api/v1/ai/situation-report/generate", {"expedition_id": expedition_id, "report_date": date})

    # ---- write tools: drafts awaiting human approval ONLY ----
    def create_alert(self, message: str, target_role: str = "EMERGENCY_COORDINATOR", severity: str = "WARNING"):
        _record("create_alert", {"message": message, "target_role": target_role}, True)
        return self._post("/api/v1/notifications", {"message": f"[AI draft — acknowledge before acting] {message}", "target_role": target_role, "severity": severity})

    def create_work_order(self, asset_id: str, problem: str, priority: str = "MEDIUM", assigned_engineer: str = ""):
        _record("create_work_order", {"asset_id": asset_id, "problem": problem}, True)
        return self._post("/api/v1/work-orders", {"asset_id": asset_id, "problem": f"[AI-DRAFT, needs engineer review] {problem}", "priority": priority, "assigned_engineer": assigned_engineer})

    def create_plan_draft(self, title: str, kind: str = "GENERAL", body: dict | None = None):
        _record("create_plan_draft", {"title": title, "kind": kind}, True)
        return self._post("/api/v1/plan-drafts", {"title": title, "kind": kind, "body": body or {}})


TOOLS: dict[str, dict] = {
    "get_person_status": {"writes": False, "desc": "Search personnel / readiness via REST"},
    "get_cargo_status": {"writes": False, "desc": "Package (BX-…) or shipment status via REST"},
    "get_inventory": {"writes": False, "desc": "Inventory levels, optional low-stock filter"},
    "get_vehicle_status": {"writes": False, "desc": "Vehicle list with asset status"},
    "get_station_capacity": {"writes": False, "desc": "Stations + expedition load estimate"},
    "get_weather_snapshot": {"writes": False, "desc": "Live weather snapshot for a station"},
    "get_active_incidents": {"writes": False, "desc": "Incidents not RESOLVED/CLOSED"},
    "get_transport_schedule": {"writes": False, "desc": "Shipments as transport schedule proxy"},
    "get_inventory_forecast": {"writes": False, "desc": "At-risk items with stockout ETA, urgency-sorted"},
    "get_missions": {"writes": False, "desc": "Field missions with status"},
    "get_incident_resources": {"writes": False, "desc": "Matched response resources for an incident"},
    "generate_situation_report": {"writes": True, "desc": "DRAFT situation report only — human must publish"},
    "create_alert": {"writes": True, "desc": "UNREAD AI advisory only — human must acknowledge"},
    "create_work_order": {"writes": True, "desc": "OPEN work order only — engineer must act"},
    "create_plan_draft": {"writes": True, "desc": "DRAFT plan only — human must APPROVE"},
}


def call_tool(client: ToolClient, name: str, args: dict):
    if name not in TOOLS:
        raise ValueError(f"unknown tool {name}")
    fn = getattr(client, name)
    allowed = {"query", "ref", "low_stock", "category", "station", "only_at_risk", "incident_id", "expedition_id", "date", "message", "target_role", "severity", "asset_id", "problem", "priority", "assigned_engineer", "title", "kind", "body"}
    return fn(**{k: v for k, v in (args or {}).items() if k in allowed})
