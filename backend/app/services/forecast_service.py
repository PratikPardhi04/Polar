"""Inventory forecasting (Phase 6.2).

Simple moving average over outflow history (ISSUE + CONSUME) in a lookback
window; reorder_point = avg_daily_use × lead_time_days + safety_stock
(safety_stock = avg_daily_use × safety_days). Exponential smoothing is
available per-item via alpha-weighted daily buckets on request.
No ML, no deep learning — deterministic and judge-explainable.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.inventory import InventoryItem, InventoryTransaction, available_stock

OUTFLOW_TYPES = ("ISSUE", "CONSUME")


def _tval(t) -> str:
    return t.value if hasattr(t, "value") else str(t)


def daily_buckets(db: Session, item_id: str, window_days: int, now: datetime) -> list[float]:
    """Outflow per day, oldest → newest, over the lookback window."""
    since = now - timedelta(days=window_days)
    rows = (
        db.query(InventoryTransaction)
        .filter(InventoryTransaction.item_id == item_id, InventoryTransaction.created_at >= since)
        .all()
    )
    buckets = [0.0] * window_days
    for txn in rows:
        if _tval(txn.txn_type) not in OUTFLOW_TYPES:
            continue
        ts = txn.created_at if txn.created_at and txn.created_at.tzinfo else (txn.created_at.replace(tzinfo=timezone.utc) if txn.created_at else now)
        day = (now - ts).days
        if 0 <= day < window_days:
            buckets[window_days - 1 - day] += txn.quantity or 0.0
    return buckets


def moving_average(buckets: list[float]) -> float:
    return sum(buckets) / len(buckets) if buckets else 0.0


def exp_smoothing(buckets: list[float], alpha: float = 0.3) -> float:
    level = buckets[0] if buckets else 0.0
    for x in buckets[1:]:
        level = alpha * x + (1 - alpha) * level
    return level


def forecast_item(db: Session, item: InventoryItem, window_days: int, lead_time_days: int, safety_days: int, method: str = "sma", now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    buckets = daily_buckets(db, item.id, window_days, now)
    rate = exp_smoothing(buckets) if method == "ewma" else moving_average(buckets)
    on_hand = item.quantity or 0.0
    avail = available_stock(on_hand, item.reserved_quantity or 0.0)
    safety_stock = rate * safety_days
    reorder_point = rate * lead_time_days + safety_stock
    days_left = (avail / rate) if rate > 0 else None
    if days_left is not None and days_left < 0:
        days_left = 0.0
    at_risk = rate > 0 and avail <= reorder_point
    return {
        "item_id": item.id,
        "name": item.name,
        "category": item.category,
        "on_hand": on_hand,
        "available": avail,
        "avg_daily_use": round(rate, 3),
        "method": method,
        "days_until_stockout": round(days_left, 1) if days_left is not None else None,
        "reorder_point": round(reorder_point, 2),
        "safety_stock": round(safety_stock, 2),
        "suggested_reorder_qty": round(max(0.0, reorder_point - avail), 2),
        "at_risk": at_risk,
    }


def forecast_all(db: Session, window_days: int = 30, lead_time_days: int = 14, safety_days: int = 7, method: str = "sma", only_at_risk: bool = False) -> dict:
    items = db.query(InventoryItem).order_by(InventoryItem.name).all()
    rows = [forecast_item(db, item, window_days, lead_time_days, safety_days, method) for item in items]
    if only_at_risk:
        rows = [r for r in rows if r["at_risk"]]
    # urgency first: at-risk sorted by stockout ETA, then the rest alphabetically
    rows.sort(key=lambda r: (0, r["days_until_stockout"] if r["days_until_stockout"] is not None else float("inf"), r["name"]) if r["at_risk"] else (1, r["name"]))
    return {"items": rows, "params": {"window_days": window_days, "lead_time_days": lead_time_days, "safety_days": safety_days, "method": method}}
