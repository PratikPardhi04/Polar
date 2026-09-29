from datetime import date

from pydantic import BaseModel, Field

from app.models.inventory import CATEGORIES, StockStatus, TxnType


class ItemCreate(BaseModel):
    name: str
    category: str = Field(default="Scientific supplies", description=f"one of {CATEGORIES}")
    unit: str = "pcs"
    location: str = "Bharati"
    expiry: date | None = None
    minimum_stock: float = 0.0
    reserved_quantity: float = 0.0


class ItemResponse(BaseModel):
    id: str
    name: str
    category: str
    quantity: float
    unit: str
    location: str
    expiry: date | None
    minimum_stock: float
    reserved_quantity: float
    status: StockStatus

    model_config = {"from_attributes": True}


class TxnCreate(BaseModel):
    item_id: str
    txn_type: TxnType
    quantity: float
    note: str = ""
    location: str | None = None


class TxnResponse(BaseModel):
    id: str
    item_id: str
    txn_type: TxnType
    quantity: float
    note: str
    location: str | None
    actor_id: str | None

    model_config = {"from_attributes": True}
