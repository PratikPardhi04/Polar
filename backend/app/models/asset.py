import enum
import uuid
from datetime import date

from sqlalchemy import Column, Date, DateTime, Enum, Float, ForeignKey, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AssetStatus(str, enum.Enum):
    PROCURED = "PROCURED"
    RECEIVED = "RECEIVED"
    COMMISSIONED = "COMMISSIONED"
    IN_SERVICE = "IN_SERVICE"
    MAINTENANCE = "MAINTENANCE"
    RETURNED_TO_SERVICE = "RETURNED_TO_SERVICE"
    RETIRED = "RETIRED"


ALLOWED_ASSET_TRANSITIONS: dict[str, set[str]] = {
    "PROCURED": {"RECEIVED"},
    "RECEIVED": {"COMMISSIONED"},
    "COMMISSIONED": {"IN_SERVICE"},
    "IN_SERVICE": {"MAINTENANCE", "RETIRED"},
    "MAINTENANCE": {"RETURNED_TO_SERVICE"},
    "RETURNED_TO_SERVICE": {"IN_SERVICE", "RETIRED"},
    "RETIRED": set(),
}


class AssetType(str, enum.Enum):
    EQUIPMENT = "EQUIPMENT"
    VEHICLE = "VEHICLE"
    INSTRUMENT = "INSTRUMENT"
    SHELTER = "SHELTER"
    OTHER = "OTHER"


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    asset_type = Column(Enum(AssetType, name="asset_type", native_enum=False), nullable=False, default=AssetType.EQUIPMENT)
    serial_number = Column(String(128), unique=True, nullable=False)
    location = Column(String(128), nullable=False, default="Goa")
    owner = Column(String(255), nullable=False, default="")
    status = Column(Enum(AssetStatus, name="asset_status", native_enum=False), nullable=False, default=AssetStatus.PROCURED)
    last_inspection = Column(Date, nullable=True)
    next_maintenance = Column(Date, nullable=True)
    runtime_hours = Column(Float, nullable=False, default=0.0)
    qr_code = Column(Text, nullable=False, default="")


class Vehicle(Base):
    """Vehicle as a specialization of Asset (shares lifecycle via assets.row)."""

    __tablename__ = "vehicles"

    id = Column(String(36), primary_key=True, default=_uuid)
    asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False, unique=True, index=True)
    registration_number = Column(String(64), nullable=False, default="")
    vehicle_type = Column(String(64), nullable=False, default="Snowmobile")
    capacity = Column(String(64), nullable=False, default="")
    fuel_type = Column(String(32), nullable=False, default="Diesel")
    odometer_km = Column(Float, nullable=False, default=0.0)


class WorkOrderPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WorkOrderStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


ALLOWED_WO_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"IN_PROGRESS", "ON_HOLD", "CLOSED"},
    "IN_PROGRESS": {"ON_HOLD", "RESOLVED", "CLOSED"},
    "ON_HOLD": {"IN_PROGRESS", "CLOSED"},
    "RESOLVED": {"CLOSED"},
    "CLOSED": set(),
}


class MaintenanceWorkOrder(Base):
    __tablename__ = "maintenance_work_orders"

    id = Column(String(36), primary_key=True, default=_uuid)
    asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False, index=True)
    problem = Column(Text, nullable=False)
    priority = Column(Enum(WorkOrderPriority, name="wo_priority", native_enum=False), nullable=False, default=WorkOrderPriority.MEDIUM)
    status = Column(Enum(WorkOrderStatus, name="wo_status", native_enum=False), nullable=False, default=WorkOrderStatus.OPEN)
    assigned_engineer = Column(String(255), nullable=False, default="")
    due_date = Column(Date, nullable=True)
    resolution = Column(Text, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
