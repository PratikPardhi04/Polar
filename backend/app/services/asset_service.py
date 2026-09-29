from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.asset import (
    ALLOWED_ASSET_TRANSITIONS,
    ALLOWED_WO_TRANSITIONS,
    Asset,
    AssetStatus,
    AssetType,
    MaintenanceWorkOrder,
    Vehicle,
)
from app.models.audit import AuditAction, AuditEvent
from app.schemas.asset import AssetCreate, AssetUpdate, VehicleCreate, WorkOrderCreate, WorkOrderUpdate
from app.services.cargo_service import make_qr_b64


def _audit(db: Session, actor_id: str | None, action: str, entity_type: str, entity_id: str, old: str | None = None, new: str | None = None, reason: str = ""):
    db.add(AuditEvent(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, old_value=old, new_value=new, reason=reason, source="SYNTHETIC_DEMO"))


def _sval(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


def create_asset(db: Session, body: AssetCreate, actor_id: str) -> Asset:
    if db.query(Asset).filter(Asset.serial_number == body.serial_number).first():
        raise HTTPException(status_code=400, detail="serial_number already exists")
    asset = Asset(**body.model_dump())
    db.add(asset)
    db.flush()
    asset.qr_code = make_qr_b64(f"POLARIS:AST:{asset.id}")
    _audit(db, actor_id, AuditAction.CREATE, "Asset", asset.id, new=f"{asset.name} PROCURED")
    db.commit()
    db.refresh(asset)
    return asset


def transition_asset(db: Session, asset: Asset, to_status: AssetStatus, actor_id: str, reason: str = "") -> Asset:
    old, new = _sval(asset.status), _sval(to_status)
    if new != old:
        if new not in ALLOWED_ASSET_TRANSITIONS.get(old, set()):
            raise HTTPException(status_code=409, detail=f"illegal asset transition {old} -> {new}")
        asset.status = to_status
        _audit(db, actor_id, AuditAction.STATUS_TRANSITION, "Asset", asset.id, old=old, new=new, reason=reason)
        db.commit()
        db.refresh(asset)
    return asset


def patch_asset(db: Session, asset: Asset, body: AssetUpdate) -> Asset:
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return asset


def create_vehicle(db: Session, body: VehicleCreate, actor_id: str) -> Vehicle:
    asset = create_asset(db, AssetCreate(name=body.name, asset_type=AssetType.VEHICLE, serial_number=body.serial_number, location=body.location, owner=body.owner), actor_id=actor_id)
    vehicle = Vehicle(asset_id=asset.id, registration_number=body.registration_number, vehicle_type=body.vehicle_type, capacity=body.capacity, fuel_type=body.fuel_type, odometer_km=body.odometer_km)
    db.add(vehicle)
    db.flush()
    _audit(db, actor_id, AuditAction.CREATE, "Vehicle", vehicle.id, new=f"asset {asset.id}")
    db.commit()
    db.refresh(vehicle)
    return vehicle


def create_work_order(db: Session, body: WorkOrderCreate, actor_id: str) -> MaintenanceWorkOrder:
    if not db.query(Asset).filter(Asset.id == body.asset_id).first():
        raise HTTPException(status_code=400, detail="unknown asset_id")
    wo = MaintenanceWorkOrder(**body.model_dump())
    db.add(wo)
    db.flush()
    _audit(db, actor_id, AuditAction.CREATE, "WorkOrder", wo.id, new=f"OPEN on {wo.asset_id}")
    db.commit()
    db.refresh(wo)
    return wo


def patch_work_order(db: Session, wo: MaintenanceWorkOrder, body: WorkOrderUpdate, actor_id: str) -> MaintenanceWorkOrder:
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        old, new = _sval(wo.status), _sval(data["status"])
        if new != old:
            if new not in ALLOWED_WO_TRANSITIONS.get(old, set()):
                raise HTTPException(status_code=409, detail=f"illegal work-order transition {old} -> {new}")
            wo.status = data.pop("status")
            _audit(db, actor_id, AuditAction.STATUS_TRANSITION, "WorkOrder", wo.id, old=old, new=new)
    for key, value in data.items():
        if key == "resolution" and value is None:
            value = ""
        setattr(wo, key, value)
    db.commit()
    db.refresh(wo)
    return wo
