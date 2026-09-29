"""Consumption plan generator (Generate Plan page).

Deterministic pipeline over LIVE backend data — no LLM guessing:
forecast (rate, stockout ETA, reorder point) + inventory levels, filtered by
plan kind, projected over a chosen horizon. The finished plan is saved as a
DRAFT plan record; a human APPROVEs it on the backend. Nothing executes here.
"""

from datetime import datetime, timezone

SAFETY_DAYS = 7
KINDS = ("FOOD", "SUPPLIES", "FULL")

# Hardcoded polar ration norms: per person per day, in the item's unit.
# These FLOOR every estimate so a missing consumption history never yields a
# "use 0" plan for a station with humans on it. Observed history still wins
# whenever it exceeds the norm. Matched by substring on the item name.
RATION_NORMS = {
    "rice": 0.35, "dal": 0.12, "freeze-dried": 1.0, "cooking oil": 0.06, "tea": 0.025,
    "diesel": 8.0, "kerosene": 2.0, "petrol": 1.0, "lpg": 0.05, "grease": 0.1,
    "medkit": 0.05, "antibiotic": 0.5, "bandage": 1.0, "oxygen": 0.02, "vaccine": 0.05,
    "aa cell": 2.0, "li-ion": 0.2, "ups batter": 0.01, "solar batter": 0.01, "torch cell": 0.5,
    "sample vial": 5.0, "filter": 1.0, "reagent": 0.5, "thermometer": 0.02, "core box": 1.0,
    "harness": 0.01, "helmet": 0.01, "flare": 0.2, "life vest": 0.01, "fire extinguisher": 0.01,
    "wrench": 0.05, "drill": 0.02, "shovel": 0.05, "saw": 0.02, "multimeter": 0.01,
    "track link": 0.2, "engine belt": 0.1, "fuse": 1.0, "bearing": 0.3, "hydraulic hose": 0.05,
    "parka": 0.01, "glove": 0.1, "boot": 0.02, "goggle": 0.05, "sleeping bag": 0.01,
    "iridium": 0.05, "vhf": 0.05, "antenna": 0.02, "cable": 0.5, "repeater": 0.01,
}
CATEGORY_NORMS = {
    "Food": 0.5, "Fuel": 6.0, "Medical": 0.2, "Batteries": 0.5,
    "Scientific supplies": 1.0, "Safety equipment": 0.1, "Tools": 0.2,
    "Spare parts": 0.5, "Cold-weather gear": 0.1, "Communication": 0.2,
}
GENERIC_NORM = 0.5
ASSUMED_CREW = 20


def _norm_for(name: str, category: str) -> float:
    lname = (name or "").lower()
    for key, val in RATION_NORMS.items():
        if key in lname:
            return val
    return CATEGORY_NORMS.get(category, GENERIC_NORM)


def _lines_for(kind: str, horizon_days: int, forecast_items: list, inventory: list, crew_size: int) -> tuple[list[dict], list[str]]:
    inv = {i.get("id"): i for i in inventory}
    lines: list[dict] = []
    for f in forecast_items:
        item = inv.get(f.get("item_id"), {})
        category = f.get("category", item.get("category", ""))
        if kind == "FOOD" and category != "Food":
            continue
        if kind == "SUPPLIES" and category == "Food":
            continue
        observed = float(f.get("avg_daily_use", 0) or 0)
        norm = _norm_for(f.get("name", ""), category) * crew_size
        rate = max(observed, norm)
        basis = "observed history" if observed >= norm and observed > 0 else "polar ration norm (hardcoded)"
        avail = float(f.get("available", 0) or 0)
        days = round(avail / rate, 1) if rate > 0 else None
        need = max(0.0, rate * horizon_days - avail)
        suggested = round(need + rate * SAFETY_DAYS, 2)
        if days is None:
            status, action = ("STABLE", "No stock pressure identified.")
            suggested = 0.0
        elif days <= horizon_days:
            status, action = ("ORDER NOW", f"Burns out in ~{days} days, inside the {horizon_days}-day horizon — raise a resupply request.")
        elif f.get("at_risk"):
            status, action = ("WATCH", "Below reorder point but survives the horizon — re-check next cycle.")
        else:
            status, action = ("OK", "Healthy through the horizon.")
            suggested = 0.0
        lines.append({
            "item_id": f.get("item_id"), "name": f.get("name"), "category": category,
            "on_hand": f.get("on_hand"), "unit": item.get("unit", "pcs"),
            "avg_daily_use": round(rate, 3), "rate_basis": basis,
            "days_left": days, "status": status,
            "suggested_qty": suggested, "action": action,
        })
    lines.sort(key=lambda l: (0 if l["status"] == "ORDER NOW" else 1 if l["status"] == "WATCH" else 2, l["days_left"] if l["days_left"] is not None else float("inf")))
    risks = [f"{l['name']} runs out in ~{l['days_left']} days — {l['suggested_qty']} {l['unit']} proposed" for l in lines if l["status"] == "ORDER NOW"][:5]
    return lines, risks


def generate_plan(client, kind: str, horizon_days: int) -> dict:
    """Fetch live data via tools, compose the plan, save it as a DRAFT."""
    kind = (kind or "").upper()
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    horizon_days = max(1, min(int(horizon_days or 14), 180))
    forecast = client.get_inventory_forecast(only_at_risk=False)
    inventory = client.get_inventory()
    try:
        crew = client.get_person_status()
        crew_size = len(crew) if isinstance(crew, list) and crew else ASSUMED_CREW
        crew_note = f"{crew_size} personnel on record" if isinstance(crew, list) and crew else f"personnel unreadable — assumed crew of {ASSUMED_CREW}"
    except Exception:
        crew_size, crew_note = ASSUMED_CREW, f"personnel unreadable — assumed crew of {ASSUMED_CREW}"
    items = (forecast or {}).get("items", []) if isinstance(forecast, dict) else []
    lines, risks = _lines_for(kind, horizon_days, items, inventory if isinstance(inventory, list) else [], crew_size)
    counts = {"ORDER NOW": 0, "WATCH": 0, "OK": 0, "STABLE": 0}
    for l in lines:
        counts[l["status"]] = counts.get(l["status"], 0) + 1
    plan = {
        "kind": kind, "horizon_days": horizon_days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "crew_size": crew_size, "crew_note": crew_note,
        "summary": {"items_covered": len(lines), **counts, "total_suggested_qty": round(sum(l["suggested_qty"] for l in lines), 2)},
        "risks": risks or ["No items burn out inside this horizon."],
        "lines": lines,
    }
    draft = client.create_plan_draft(
        title=f"{kind.title()} consumption plan — {horizon_days}d horizon",
        kind="INVENTORY",
        body={"planner": "ai-plan-generator", **{k: v for k, v in plan.items() if k != "lines"}, "lines": lines},
    )
    plan["plan_draft_id"] = draft.get("id")
    plan["approval_note"] = "Saved as DRAFT — a human must APPROVE it (POST /api/v1/plan-drafts/{id}/decide). Nothing was ordered."
    return plan
