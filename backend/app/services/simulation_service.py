"""Failure simulation (Phase 8.2, admin-only).

Every scenario mutates REAL records through the REAL state machines, so the
dashboard, notifications, AI panel, and audit log react exactly as they would
to a genuine event. Nothing here is a mock.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditEvent
from app.models.cargo import CargoStatus, Shipment
from app.models.checkin import FieldCheckIn
from app.models.inventory import InventoryItem, available_stock
from app.models.mission import FieldMission
from app.models.notification import NotificationType, Severity
from app.models.station import Station
from app.models.weather import WeatherSnapshot
from app.schemas.sync import SyncBatchRequest, SyncEventIn
from app.services import cargo_service, checkin_service, inventory_service, sync_service
from app.services.notification_service import notify_once


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def simulate_cargo_delay(db: Session, actor_id: str, shipment_id: str | None = None) -> dict:
    ship = None
    if shipment_id:
        ship = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not ship:
            raise HTTPException(status_code=404, detail="shipment not found")
    else:
        ship = db.query(Shipment).filter(Shipment.status == CargoStatus.IN_TRANSIT).first()
        if not ship:
            raise HTTPException(status_code=409, detail="no IN_TRANSIT shipment to delay")
    cargo_service.transition_shipment(db, ship, CargoStatus.DELAYED, actor_id=actor_id, reason="SIMULATION: logistics delay")
    return {"shipment_id": ship.id, "status": "DELAYED"}


def simulate_network_outage(db: Session, actor_id: str, online: bool) -> dict:
    del db
    os.environ["NETWORK_STATUS"] = "ONLINE" if online else "OFFLINE"
    return {"network": os.environ["NETWORK_STATUS"], "note": "SIMULATED flag read by GET /api/v1/dashboard/summary"}


def simulate_missed_checkin(db: Session, actor_id: str, mission_id: str | None = None) -> dict:
    _ = actor_id
    mission = None
    if mission_id:
        mission = db.query(FieldMission).filter(FieldMission.id == mission_id).first()
        if not mission:
            raise HTTPException(status_code=404, detail="mission not found")
    else:
        mission = db.query(FieldMission).filter(FieldMission.status.in_(["DEPLOYED", "ACTIVE"])).first()
        if not mission:
            raise HTTPException(status_code=409, detail="no DEPLOYED/ACTIVE mission to miss a check-in on")
    ci = FieldCheckIn(mission_id=mission.id, due_at=datetime.now(timezone.utc) - timedelta(hours=2))
    db.add(ci)
    db.commit()
    out = checkin_service.advance_checkins(db)
    return {"mission_id": mission.id, "check_in_id": ci.id, "advanced": out["advanced"]}


def trigger_sos(db: Session, actor_id: str, mission_id: str | None = None, personnel_id: str | None = None) -> dict:
    mission = None
    if mission_id:
        mission = db.query(FieldMission).filter(FieldMission.id == mission_id).first()
        if not mission:
            raise HTTPException(status_code=404, detail="mission not found")
    else:
        mission = db.query(FieldMission).filter(FieldMission.status.in_(["DEPLOYED", "ACTIVE"])).first()
        if not mission:
            raise HTTPException(status_code=409, detail="no DEPLOYED/ACTIVE mission for SOS")
    ev = SyncEventIn(
        event_id=f"sim-sos-{uuid.uuid4().hex[:8]}", device_id="SIM-CONTROL", user_id="sim",
        event_type="SOS", entity_id=mission.id, timestamp=_now_iso(),
        payload={"personnel_id": personnel_id, "mission_id": mission.id, "location": "SIMULATED WP-9", "battery_pct": 41, "comm_status": "simulated-weak", "note": "SIMULATION: triggered from control panel"},
    )
    resp = sync_service.process_batch(db, SyncBatchRequest(events=[ev]), actor_id=actor_id)
    return {"mission_id": mission.id, "sos_alerts": [a.model_dump() for a in resp.sos_alerts], "errors": [e.model_dump() for e in resp.errors]}


def simulate_inventory_shortage(db: Session, actor_id: str, item_id: str | None = None) -> dict:
    item = None
    if item_id:
        item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="item not found")
    else:
        for cand in db.query(InventoryItem).order_by(InventoryItem.quantity.desc()).all():
            if available_stock(cand.quantity or 0, cand.reserved_quantity or 0) > (cand.minimum_stock or 0):
                item = cand
                break
        if not item:
            raise HTTPException(status_code=409, detail="no item with headroom to shortage")
    avail = available_stock(item.quantity or 0, item.reserved_quantity or 0)
    qty = max(1.0, avail - (item.minimum_stock or 0) + 1.0)
    item, _ = inventory_service.apply_transaction(db, item.id, "ISSUE", qty, actor_id=actor_id, note="SIMULATION: demand spike")
    return {"item_id": item.id, "name": item.name, "quantity_left": item.quantity, "status": item.status.value if hasattr(item.status, "value") else str(item.status)}


def simulate_weather_event(db: Session, actor_id: str, station_ref: str = "BHARATI") -> dict:
    station = db.query(Station).filter((Station.id == station_ref) | (Station.code == station_ref.upper())).first()
    if not station:
        raise HTTPException(status_code=404, detail=f"unknown station {station_ref}")
    snap = WeatherSnapshot(station_id=station.id, temp_c=-38.0, wind_kph=95.0, visibility_m=400.0, condition="SEVERE", source="SYNTHETIC_DEMO")
    db.add(snap)
    db.flush()
    notify_once(db, NotificationType.WEATHER_ALERT, Severity.CRITICAL, "FIELD_LEADER", "WeatherSnapshot", snap.id, f"SIMULATION: severe weather over {station.code} — wind 95 kph, vis 400 m. Go/No-Go weather check will now FAIL.")
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.CREATE, entity_type="WeatherSnapshot", entity_id=snap.id, new_value="SIMULATED SEVERE", source="SYNTHETIC_DEMO"))
    db.commit()
    return {"station": station.code, "condition": "SEVERE", "wind_kph": 95.0, "note": "Go/No-Go weather check now fails; WEATHER_ALERT issued"}
