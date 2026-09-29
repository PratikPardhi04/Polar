from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.asset import Asset, MaintenanceWorkOrder, Vehicle
from app.models.audit import AuditEvent
from app.models.user import Role, User
from app.schemas.asset import (
    AssetCreate,
    AssetResponse,
    AssetStatusUpdate,
    AssetUpdate,
    VehicleCreate,
    VehicleResponse,
    WorkOrderCreate,
    WorkOrderResponse,
    WorkOrderUpdate,
)
from app.services.asset_service import create_asset, create_vehicle, create_work_order, patch_asset, patch_work_order, transition_asset

router = APIRouter(prefix="/api/v1", tags=["assets"])

_write = require_role(Role.ADMIN, Role.ENGINEER, Role.LOGISTICS_OFFICER)


@router.post("/assets", response_model=AssetResponse, status_code=201)
def create(body: AssetCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return create_asset(db, body, actor_id=user.id)


@router.get("/assets", response_model=list[AssetResponse])
def list_assets(db: Session = Depends(get_db), _: User = Depends(get_current_user), status: str | None = Query(default=None)):
    q = db.query(Asset)
    if status:
        q = q.filter(Asset.status == status)
    return q.order_by(Asset.name).all()


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset(asset_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    return asset


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
def patch(asset_id: str, body: AssetUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    return patch_asset(db, asset, body)


@router.patch("/assets/{asset_id}/status", response_model=AssetResponse)
def asset_status(asset_id: str, body: AssetStatusUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    return transition_asset(db, asset, body.to_status, actor_id=user.id, reason=body.reason)


@router.get("/assets/{asset_id}/history")
def asset_history(asset_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if not db.query(Asset).filter(Asset.id == asset_id).first():
        raise HTTPException(status_code=404, detail="asset not found")
    events = db.query(AuditEvent).filter(AuditEvent.entity_type == "Asset", AuditEvent.entity_id == asset_id).order_by(AuditEvent.created_at).all()
    work_orders = db.query(MaintenanceWorkOrder).filter(MaintenanceWorkOrder.asset_id == asset_id).order_by(MaintenanceWorkOrder.created_at).all()
    return {
        "transitions": [{"action": e.action, "old": e.old_value, "new": e.new_value, "at": str(e.created_at)} for e in events],
        "work_orders": [w.id for w in work_orders],
    }


@router.post("/vehicles", response_model=VehicleResponse, status_code=201)
def create_veh(body: VehicleCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    v = create_vehicle(db, body, actor_id=user.id)
    return VehicleResponse(id=v.id, asset_id=v.asset_id, registration_number=v.registration_number, vehicle_type=v.vehicle_type, capacity=v.capacity, fuel_type=v.fuel_type, odometer_km=v.odometer_km, asset=db.query(Asset).filter(Asset.id == v.asset_id).first())


@router.get("/vehicles", response_model=list[VehicleResponse])
def list_veh(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    out = []
    for v in db.query(Vehicle).all():
        out.append(VehicleResponse(id=v.id, asset_id=v.asset_id, registration_number=v.registration_number, vehicle_type=v.vehicle_type, capacity=v.capacity, fuel_type=v.fuel_type, odometer_km=v.odometer_km, asset=db.query(Asset).filter(Asset.id == v.asset_id).first()))
    return out


@router.post("/work-orders", response_model=WorkOrderResponse, status_code=201)
def create_wo(body: WorkOrderCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return create_work_order(db, body, actor_id=user.id)


@router.get("/work-orders", response_model=list[WorkOrderResponse])
def list_wo(db: Session = Depends(get_db), _: User = Depends(get_current_user), asset_id: str | None = None, status: str | None = None):
    q = db.query(MaintenanceWorkOrder)
    if asset_id:
        q = q.filter(MaintenanceWorkOrder.asset_id == asset_id)
    if status:
        q = q.filter(MaintenanceWorkOrder.status == status)
    return q.order_by(MaintenanceWorkOrder.created_at).all()


@router.get("/work-orders/{wo_id}", response_model=WorkOrderResponse)
def get_wo(wo_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    wo = db.query(MaintenanceWorkOrder).filter(MaintenanceWorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    return wo


@router.patch("/work-orders/{wo_id}", response_model=WorkOrderResponse)
def patch_wo(wo_id: str, body: WorkOrderUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    wo = db.query(MaintenanceWorkOrder).filter(MaintenanceWorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    return patch_work_order(db, wo, body, actor_id=user.id)
