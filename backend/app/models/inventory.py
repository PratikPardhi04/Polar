import enum
import uuid
from datetime import date

from sqlalchemy import Column, Date, DateTime, Enum, Float, ForeignKey, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


CATEGORIES = [
    "Food",
    "Fuel",
    "Medical",
    "Batteries",
    "Scientific supplies",
    "Safety equipment",
    "Tools",
    "Spare parts",
    "Cold-weather gear",
    "Communication",
]


class StockStatus(str, enum.Enum):
    OK = "OK"
    WATCH = "WATCH"
    CRITICAL = "CRITICAL"


class TxnType(str, enum.Enum):
    RECEIVE = "RECEIVE"
    ISSUE = "ISSUE"
    RETURN = "RETURN"
    CONSUME = "CONSUME"
    TRANSFER = "TRANSFER"
    ADJUST = "ADJUST"


# txn types that decrement sellable stock
DECREMENT_TYPES = {TxnType.ISSUE.value, TxnType.CONSUME.value}


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(64), nullable=False, default="Scientific supplies")
    quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String(32), nullable=False, default="pcs")
    location = Column(String(128), nullable=False, default="Bharati")
    expiry = Column(Date, nullable=True)
    minimum_stock = Column(Float, nullable=False, default=0.0)
    reserved_quantity = Column(Float, nullable=False, default=0.0)
    status = Column(Enum(StockStatus, name="stock_status", native_enum=False), nullable=False, default=StockStatus.OK)


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(String(36), primary_key=True, default=_uuid)
    item_id = Column(String(36), ForeignKey("inventory_items.id"), nullable=False, index=True)
    txn_type = Column(Enum(TxnType, name="txn_type", native_enum=False), nullable=False)
    quantity = Column(Float, nullable=False)
    note = Column(Text, nullable=True, default="")
    location = Column(String(128), nullable=True)  # TRANSFER destination / txn site
    actor_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def compute_status(quantity: float, minimum_stock: float) -> StockStatus:
    if quantity <= minimum_stock:
        return StockStatus.CRITICAL
    if minimum_stock > 0 and quantity <= minimum_stock * 1.5:
        return StockStatus.WATCH
    return StockStatus.OK


def available_stock(quantity: float, reserved: float) -> float:
    return (quantity or 0.0) - (reserved or 0.0)


def validate_issue(quantity: float, reserved: float, requested: float) -> tuple[bool, str]:
    """Isolated over-issue check — Phase 3 offline conflict detection reuses this."""
    if requested <= 0:
        return False, "quantity must be positive"
    avail = available_stock(quantity, reserved)
    if requested > avail:
        return False, f"insufficient stock: requested {requested}, available {avail} (on hand {quantity}, reserved {reserved})"
    return True, ""
