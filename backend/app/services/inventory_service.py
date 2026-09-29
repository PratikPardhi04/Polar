from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditEvent
from app.models.inventory import InventoryItem, InventoryTransaction, TxnType, available_stock, compute_status, validate_issue


def _tval(t) -> str:
    return t.value if hasattr(t, "value") else str(t)


def create_item(db: Session, actor_id: str, **fields) -> InventoryItem:
    item = InventoryItem(**fields)
    item.status = compute_status(item.quantity or 0.0, item.minimum_stock or 0.0)
    db.add(item)
    db.flush()
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.CREATE, entity_type="InventoryItem", entity_id=item.id, new_value=f"{item.name} qty={item.quantity}", source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(item)
    return item


def apply_transaction(db: Session, item_id: str, txn_type: TxnType, quantity: float, actor_id: str, note: str = "", location: str | None = None) -> tuple[InventoryItem, InventoryTransaction]:
    """Single service-layer transaction writes BOTH the transaction row AND the derived quantity.

    Application code must never mutate InventoryItem.quantity directly.
    """
    ttype = _tval(txn_type)
    if quantity <= 0 and ttype != TxnType.ADJUST.value:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="inventory item not found")

    old_qty = item.quantity or 0.0
    old_status = _tval(item.status)
    if ttype in (TxnType.RECEIVE.value, TxnType.RETURN.value):
        item.quantity = old_qty + quantity
    elif ttype in (TxnType.ISSUE.value, TxnType.CONSUME.value):
        ok, why = validate_issue(old_qty, item.reserved_quantity or 0.0, quantity)
        if not ok:
            raise HTTPException(status_code=400, detail=why)
        item.quantity = old_qty - quantity
    elif ttype == TxnType.ADJUST.value:
        new_qty = old_qty + quantity
        if new_qty < 0:
            raise HTTPException(status_code=400, detail=f"adjustment would drive stock negative ({old_qty} + {quantity})")
        item.quantity = new_qty
    elif ttype == TxnType.TRANSFER.value:
        if location:
            item.location = location
    else:
        raise HTTPException(status_code=400, detail=f"unknown txn type {ttype}")

    item.status = compute_status(item.quantity, item.minimum_stock or 0.0)
    if _tval(item.status) == "CRITICAL" and old_status != "CRITICAL":
        from app.services.notification_service import notify_once
        from app.models.notification import NotificationType, Severity

        notify_once(
            db, NotificationType.STOCK_CRITICAL, Severity.CRITICAL, "INVENTORY_MANAGER", "InventoryItem", item.id,
            f"{item.name} CRITICAL: {item.quantity:g} {item.unit} left (min {item.minimum_stock:g}) at {item.location}",
        )
    txn = InventoryTransaction(item_id=item.id, txn_type=txn_type, quantity=quantity, note=note, location=location, actor_id=actor_id)
    db.add(txn)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=actor_id,
            action=AuditAction.STATUS_TRANSITION,
            entity_type="InventoryItem",
            entity_id=item.id,
            old_value=f"qty={old_qty}",
            new_value=f"qty={item.quantity} via {ttype}",
            reason=note,
            source="SYNTHETIC_DEMO",
        )
    )
    db.commit()
    db.refresh(item)
    db.refresh(txn)
    return item, txn
