from datetime import date

from pydantic import BaseModel

from app.models.asset import AssetStatus, AssetType, WorkOrderPriority, WorkOrderStatus


class AssetCreate(BaseModel):
    name: str
    asset_type: AssetType = AssetType.EQUIPMENT
    serial_number: str
    location: str = "Goa"
    owner: str = ""
    last_inspection: date | None = None
    next_maintenance: date | None = None
    runtime_hours: float = 0.0


class AssetUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    owner: str | None = None
    last_inspection: date | None = None
    next_maintenance: date | None = None
    runtime_hours: float | None = None


class AssetStatusUpdate(BaseModel):
    to_status: AssetStatus
    reason: str = ""


class AssetResponse(BaseModel):
    id: str
    name: str
    asset_type: AssetType
    serial_number: str
    location: str
    owner: str
    status: AssetStatus
    last_inspection: date | None
    next_maintenance: date | None
    runtime_hours: float
    qr_code: str

    model_config = {"from_attributes": True}


class VehicleCreate(BaseModel):
    name: str
    serial_number: str
    location: str = "Goa"
    owner: str = ""
    registration_number: str = ""
    vehicle_type: str = "Snowmobile"
    capacity: str = ""
    fuel_type: str = "Diesel"
    odometer_km: float = 0.0


class VehicleResponse(BaseModel):
    id: str
    asset_id: str
    registration_number: str
    vehicle_type: str
    capacity: str
    fuel_type: str
    odometer_km: float
    asset: AssetResponse | None = None

    model_config = {"from_attributes": True}


class WorkOrderCreate(BaseModel):
    asset_id: str
    problem: str
    priority: WorkOrderPriority = WorkOrderPriority.MEDIUM
    assigned_engineer: str = ""
    due_date: date | None = None


class WorkOrderUpdate(BaseModel):
    problem: str | None = None
    priority: WorkOrderPriority | None = None
    status: WorkOrderStatus | None = None
    assigned_engineer: str | None = None
    due_date: date | None = None
    resolution: str | None = None


class WorkOrderResponse(BaseModel):
    id: str
    asset_id: str
    problem: str
    priority: WorkOrderPriority
    status: WorkOrderStatus
    assigned_engineer: str
    due_date: date | None
    resolution: str

    model_config = {"from_attributes": True}
