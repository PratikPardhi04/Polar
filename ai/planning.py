"""Consumption plan generator (Generate Plan page).

Deterministic pipeline over LIVE backend data — no LLM guessing:
forecast (rate, stockout ETA, reorder point) + inventory levels, filtered by
plan kind, projected over a chosen horizon. The finished plan is saved as a
DRAFT plan record; a human APPROVEs it on the backend. Nothing executes here.
"""

from datetime import datetime, timezone

SAFETY_DAYS = 7
KINDS = ("FOOD", "SUPPLIES", "FULL")


def _lines_for(kind: str, horizon_days: int, forecast_items: list, inventory: list) -> tuple[list[dict], list[str]]:
    inv = {i.get("id"): i for i in inventory}
    lines: list[dict] = []
    for f in forecast_items:
        item = inv.get(f.get("item_id"), {})
        category = f.get("category", item.get("category", ""))
        if kind == "FOOD" and category != "Food":
            continue
        if kind == "SUPPLIES" and category == "Food":
            continue
        rate = float(f.get("avg_daily_use", 0) or 0)
        avail = float(f.get("available", 0) or 0)
        days = f.get("days_until_stockout")
        need = max(0.0, rate * horizon_days - avail)
        suggested = round(need + rate * SAFETY_DAYS, 2)
        if days is None:
            status, action = ("STABLE", "No recorded consumption — no order proposed.")
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
            "avg_daily_use": rate, "days_left": days, "status": status,
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
    items = (forecast or {}).get("items", []) if isinstance(forecast, dict) else []
    lines, risks = _lines_for(kind, horizon_days, items, inventory if isinstance(inventory, list) else [])
    counts = {"ORDER NOW": 0, "WATCH": 0, "OK": 0, "STABLE": 0}
    for l in lines:
        counts[l["status"]] = counts.get(l["status"], 0) + 1
    plan = {
        "kind": kind, "horizon_days": horizon_days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
