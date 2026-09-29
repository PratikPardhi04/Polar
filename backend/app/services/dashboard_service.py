import os

from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from app.models.cargo import Package, Shipment
from app.models.inventory import InventoryItem
from app.models.personnel import Personnel
from app.schemas.dashboard import DashboardSummary

# statuses that count as "in transit" for the Mission Control card
IN_TRANSIT_STATES = {"DISPATCHED", "IN_TRANSIT", "AT_GATEWAY", "LOADED", "ARRIVED_ANTARCTICA", "RECEIVED_AT_STATION"}


def _count_if_table(db: Session, table: str, where: str, params: dict | None = None) -> int:
    try:
        tables = set(inspect(db.get_bind()).get_table_names())
    except Exception:
        return 0
    if table not in tables:
        return 0
    try:
        row = db.execute(__import__("sqlalchemy").text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), params or {}).first()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def build_summary(db: Session) -> DashboardSummary:
    personnel_total = db.query(func.count(Personnel.id)).scalar() or 0
    rows = db.query(Personnel.current_readiness, func.count()).group_by(Personnel.current_readiness).all()
    breakdown = {(r[0].value if hasattr(r[0], "value") else str(r[0])): r[1] for r in rows}

    cargo_in_transit = db.query(func.count(Shipment.id)).filter(Shipment.status.in_(list(IN_TRANSIT_STATES))).scalar() or 0
    packages_in_transit = db.query(func.count(Package.id)).filter(Package.status.in_(list(IN_TRANSIT_STATES))).scalar() or 0
    critical_inventory = db.query(func.count(InventoryItem.id)).filter(InventoryItem.status == "CRITICAL").scalar() or 0
    watch_inventory = db.query(func.count(InventoryItem.id)).filter(InventoryItem.status == "WATCH").scalar() or 0

    # Phase 4/5 tables — 0 until those phases land (forward-compatible)
    active_missions = 0
    for table in ("field_missions", "fieldmissions", "missions"):
        n = _count_if_table(db, table, "status = 'ACTIVE'")
        if n or table in (set(inspect(db.get_bind()).get_table_names()) if db.get_bind() else set()):
            active_missions = n
            break
    open_incidents = 0
    for table in ("incidents",):
        n = _count_if_table(db, table, "status NOT IN ('RESOLVED','CLOSED')")
        open_incidents = n
        break

    action_required = _count_if_table(db, "sync_conflicts", "status = 'OPEN'")

    return DashboardSummary(
        personnel_total=personnel_total,
        readiness_breakdown=breakdown,
        cargo_in_transit=cargo_in_transit,
        packages_in_transit=packages_in_transit,
        critical_inventory=critical_inventory,
        watch_inventory=watch_inventory,
        active_field_missions=active_missions,
        open_incidents=open_incidents,
        action_required=action_required,
        network=os.getenv("NETWORK_STATUS", "ONLINE"),
    )
