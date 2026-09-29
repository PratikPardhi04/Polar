"""Backend tools as LangChain @tools (addendum A.2).

Each tool is a thin wrapper around a FastAPI call — never the database
directly. Single-purpose; the docstring states what it returns and when to
call it, because the model relies entirely on the docstring.

READ-ONLY by design: the LLM-facing toolset has no writes. Draft creation
(plan drafts, advisories, work orders) happens in deterministic Python graph
nodes, never as an autonomous model tool call.
"""

import httpx
from langchain_core.tools import tool

from .settings import settings


def _headers() -> dict:
    tok = settings.AI_SERVICE_TOKEN
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _get(path: str, params: dict | None = None, timeout: float = 10.0):
    r = httpx.get(f"{settings.BACKEND_URL}{path}", params=params, headers=_headers(), timeout=timeout)
    r.raise_for_status()
    return r.json()


@tool
def get_inventory(category: str | None = None) -> list:
    """Return current inventory items (name, quantity, minimum_stock, status), optionally filtered by category. Use this before answering any question about stock levels."""
    return _get("/api/v1/inventory", params={"category": category} if category else None)


@tool
def get_person_status(query: str = "") -> list:
    """Return personnel with readiness states, optionally filtered by name/email. Use this before answering any question about crew readiness."""
    return _get("/api/v1/personnel", params={"q": query} if query else None)


@tool
def get_cargo_status(ref: str) -> dict:
    """Return status and location of one package (BX-… id) or shipment. Use this before answering any question about cargo."""
    ref = (ref or "").strip()
    if ref.upper().startswith("BX-") or ref.upper().startswith("POLARIS:"):
        pid = ref.split("POLARIS:")[-1].strip()
        return _get(f"/api/v1/packages/{pid}")
    return _get(f"/api/v1/shipments/{ref}")


@tool
def get_vehicle_status() -> list:
    """Return vehicles with asset status. Use this before answering any question about transport availability."""
    return _get("/api/v1/vehicles")


@tool
def get_station_capacity() -> dict:
    """Return stations plus expedition load per station (capacity estimate). Use this before answering station-capacity questions."""
    stations = _get("/api/v1/stations")
    expeditions = _get("/api/v1/expeditions")
    by_station: dict[str, int] = {}
    for e in expeditions:
        sid = e.get("primary_station_id", "?")
        by_station[sid] = by_station.get(sid, 0) + 1
    return {"note": "estimate: expeditions per station (no berth model yet)", "stations": stations, "expeditions_per_station": by_station}


@tool
def get_weather_snapshot(station: str) -> dict:
    """Return the live weather snapshot (temp, wind, condition) for a station code like BHARATI. Use this before answering any weather or Go/No-Go question."""
    return _get(f"/api/v1/weather/{station}")


@tool
def get_active_incidents() -> list:
    """Return incidents that are not RESOLVED/CLOSED. Use this before answering any emergency question."""
    all_inc = _get("/api/v1/incidents")
    return [i for i in all_inc if i.get("status") not in ("RESOLVED", "CLOSED")]


@tool
def get_transport_schedule() -> list:
    """Return shipments as origin → destination with status and location. Use this before answering any cargo-movement question."""
    ships = _get("/api/v1/shipments")
    return [{"id": s["id"], "route": f"{s['origin']} -> {s['destination']}", "status": s["status"], "location": s["current_location"]} for s in ships]


@tool
def get_missions() -> list:
    """Return field missions with status. Use this before answering any field-operation question."""
    return _get("/api/v1/field-missions")


@tool
def get_incident_resources(incident_id: str) -> dict:
    """Return matched response resources (crew, vehicles) for an incident id. Use this before recommending who should respond."""
    return _get(f"/api/v1/incidents/{incident_id}/resources")


@tool
def get_inventory_forecast() -> dict:
    """Return at-risk inventory items with stockout ETA, urgency-sorted. Use this before answering what runs out first."""
    return _get("/api/v1/ai/inventory-forecast", params={"only_at_risk": "true"})


#: Name → tool for deterministic server-side execution of model-proposed calls.
TOOL_MAP = {t.name: t for t in [get_inventory, get_person_status, get_cargo_status, get_vehicle_status, get_station_capacity, get_weather_snapshot, get_active_incidents, get_transport_schedule, get_missions, get_incident_resources, get_inventory_forecast]}
