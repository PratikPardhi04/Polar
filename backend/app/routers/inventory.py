from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.inventory import CATEGORIES, InventoryItem, InventoryTransaction
from app.models.user import Role, User
from app.schemas.inventory import ItemCreate, ItemResponse, TxnCreate, TxnResponse
from app.services.inventory_service import apply_transaction, create_item

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])

_write = require_role(Role.ADMIN, Role.INVENTORY_MANAGER, Role.LOGISTICS_OFFICER)


@router.get("/categories", response_model=list[str])
def categories(_: User = Depends(get_current_user)):
    return CATEGORIES


@router.post("/items", response_model=ItemResponse, status_code=201)
def create(body: ItemCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return create_item(db, actor_id=user.id, **body.model_dump())


@router.get("", response_model=list[ItemResponse])
def list_all(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    low_stock: bool = Query(default=False, description="only WATCH/CRITICAL"),
):
    query = db.query(InventoryItem)
    if category:
        query = query.filter(InventoryItem.category == category)
    if status:
        query = query.filter(InventoryItem.status == status)
    if low_stock:
        query = query.filter(InventoryItem.status != "OK")
    return query.order_by(InventoryItem.name).all()


@router.get("/{item_id}", response_model=ItemResponse)
def get_one(item_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="inventory item not found")
    return item


@router.post("/transactions", response_model=TxnResponse, status_code=201)
def transact(body: TxnCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    _, txn = apply_transaction(db, body.item_id, body.txn_type, body.quantity, actor_id=user.id, note=body.note, location=body.location)
    return txn


@router.get("/{item_id}/history", response_model=list[TxnResponse])
def history(item_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if not db.query(InventoryItem).filter(InventoryItem.id == item_id).first():
        raise HTTPException(status_code=404, detail="inventory item not found")
    return db.query(InventoryTransaction).filter(InventoryTransaction.item_id == item_id).order_by(InventoryTransaction.created_at).all()
