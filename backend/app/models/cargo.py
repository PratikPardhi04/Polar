import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class CargoStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    DECLARED = "DECLARED"
    VERIFIED = "VERIFIED"
    PACKED = "PACKED"
    INSPECTED = "INSPECTED"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    AT_GATEWAY = "AT_GATEWAY"
    LOADED = "LOADED"
    ARRIVED_ANTARCTICA = "ARRIVED_ANTARCTICA"
    RECEIVED_AT_STATION = "RECEIVED_AT_STATION"
    STORED = "STORED"
    # exceptions — reachable from any non-terminal normal state
    DELAYED = "DELAYED"
    DAMAGED = "DAMAGED"
    MISSING = "MISSING"
    QUARANTINED = "QUARANTINED"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"


NORMAL_FLOW = [
    "DRAFT", "DECLARED", "VERIFIED", "PACKED", "INSPECTED", "DISPATCHED",
    "IN_TRANSIT", "AT_GATEWAY", "LOADED", "ARRIVED_ANTARCTICA",
    "RECEIVED_AT_STATION", "STORED",
]
EXCEPTIONS = {"DELAYED", "DAMAGED", "MISSING", "QUARANTINED", "RETURNED", "CANCELLED"}
TERMINAL = {"STORED", "CANCELLED", "RETURNED"}

# recovery out of exception states (resume or terminate)
RECOVERY: dict[str, set[str]] = {
    "DELAYED": {"IN_TRANSIT", "CANCELLED"},
    "DAMAGED": {"QUARANTINED", "RETURNED", "CANCELLED"},
    "MISSING": {"IN_TRANSIT", "RETURNED", "CANCELLED"},
    "QUARANTINED": {"INSPECTED", "RETURNED", "CANCELLED"},
    "RETURNED": {"CANCELLED"},
    "CANCELLED": set(),
}


def allowed_cargo_transition(old: str, new: str) -> bool:
    if old == new:
        return True
    if old in TERMINAL:
        return False
    if old in RECOVERY:
        return new in RECOVERY[old]
    # normal state: next step forward, or any exception
    if new in EXCEPTIONS:
        return True
    try:
        return NORMAL_FLOW.index(new) == NORMAL_FLOW.index(old) + 1
    except ValueError:
        return False


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(String(36), primary_key=True, default=_uuid)
    expedition_id = Column(String(64), ForeignKey("expeditions.id"), nullable=False, index=True)
    origin = Column(String(128), nullable=False, default="Goa")
    destination = Column(String(128), nullable=False, default="Bharati")
    status = Column(Enum(CargoStatus, name="cargo_status", native_enum=False), nullable=False, default=CargoStatus.DRAFT)
    current_location = Column(String(128), nullable=False, default="Goa")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Container(Base):
    __tablename__ = "containers"

    id = Column(String(36), primary_key=True, default=_uuid)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=False, index=True)
    code = Column(String(64), unique=True, nullable=False)
    location = Column(String(128), nullable=False, default="Goa")


class Package(Base):
    __tablename__ = "packages"

    id = Column(String(32), primary_key=True)  # BX-46-2026-000001
    container_id = Column(String(36), ForeignKey("containers.id"), nullable=False, index=True)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    weight_kg = Column(Float, nullable=False, default=0.0)
    status = Column(Enum(CargoStatus, name="cargo_status", native_enum=False), nullable=False, default=CargoStatus.DRAFT)
    location = Column(String(128), nullable=False, default="Goa")
    qr_code = Column(Text, nullable=False, default="")  # base64 PNG


class CargoItem(Base):
    __tablename__ = "cargo_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    package_id = Column(String(32), ForeignKey("packages.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    unit = Column(String(32), nullable=False, default="pcs")
    category = Column(String(64), nullable=False, default="Scientific supplies")


class DocType(str, enum.Enum):
    CARGO_DECLARATION = "CARGO_DECLARATION"
    HAZMAT_DECLARATION = "HAZMAT_DECLARATION"
    PACKING_LIST = "PACKING_LIST"


class DocStatus(str, enum.Enum):
    GENERATED = "GENERATED"
    APPROVED = "APPROVED"


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=False, index=True)
    package_id = Column(String(32), ForeignKey("packages.id"), nullable=True)
    doc_type = Column(Enum(DocType, name="doc_type", native_enum=False), nullable=False)
    status = Column(Enum(DocStatus, name="doc_status", native_enum=False), nullable=False, default=DocStatus.GENERATED)
    pdf_path = Column(String(512), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


REQUIRED_DOCS_FOR_PACKED = {DocType.CARGO_DECLARATION.value, DocType.PACKING_LIST.value}
