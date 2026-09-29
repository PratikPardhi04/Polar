import base64
import io
import os
import re

import qrcode
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditEvent
from app.models.cargo import (
    REQUIRED_DOCS_FOR_PACKED,
    CargoItem,
    CargoStatus,
    Container,
    DocStatus,
    DocType,
    Document,
    Package,
    Shipment,
    allowed_cargo_transition,
)


def _status_val(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


def _audit(db: Session, actor_id: str | None, action: str, entity_type: str, entity_id: str, old: str | None = None, new: str | None = None, reason: str = ""):
    db.add(AuditEvent(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, old_value=old, new_value=new, reason=reason, source="SYNTHETIC_DEMO"))


def _expedition_tag(expedition_id: str) -> tuple[str, str]:
    nums = re.findall(r"\d+", expedition_id or "")
    num = nums[0] if nums else "00"
    year = nums[-1] if nums else "2026"
    return num, year


def make_qr_b64(payload: str) -> str:
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def next_package_id(db: Session, expedition_id: str) -> str:
    num, year = _expedition_tag(expedition_id)
    seq = db.query(Package).count() + 1
    while True:
        pid = f"BX-{num}-{year}-{seq:06d}"
        if not db.query(Package).filter(Package.id == pid).first():
            return pid
        seq += 1


def create_shipment(db: Session, expedition_id: str, origin: str, destination: str, actor_id: str) -> Shipment:
    from app.models.expedition import Expedition

    if not db.query(Expedition).filter(Expedition.id == expedition_id).first():
        raise HTTPException(status_code=400, detail=f"unknown expedition {expedition_id}")
    ship = Shipment(expedition_id=expedition_id, origin=origin, destination=destination, status=CargoStatus.DRAFT, current_location=origin)
    db.add(ship)
    db.flush()
    _audit(db, actor_id, AuditAction.CREATE, "Shipment", ship.id, new="DRAFT")
    db.commit()
    db.refresh(ship)
    return ship


def shipment_has_required_docs(db: Session, shipment_id: str) -> bool:
    have = {r[0].value if hasattr(r[0], "value") else str(r[0]) for r in db.query(Document.doc_type).filter(Document.shipment_id == shipment_id).all()}
    return REQUIRED_DOCS_FOR_PACKED <= have


def transition_shipment(db: Session, ship: Shipment, to_status: CargoStatus, actor_id: str, reason: str = "", location: str | None = None) -> Shipment:
    old = _status_val(ship.status)
    new = _status_val(to_status)
    if not allowed_cargo_transition(old, new):
        raise HTTPException(status_code=409, detail=f"illegal cargo transition {old} -> {new}")
    if old == "VERIFIED" and new == "PACKED" and not shipment_has_required_docs(db, ship.id):
        raise HTTPException(status_code=409, detail="VERIFIED -> PACKED blocked: required CARGO_DECLARATION + PACKING_LIST missing for this shipment")
    ship.status = to_status
    if location:
        ship.current_location = location
    _audit(db, actor_id, AuditAction.STATUS_TRANSITION, "Shipment", ship.id, old=old, new=new, reason=reason)
    if new == "DELAYED":
        from app.models.notification import NotificationType, Severity
        from app.services.notification_service import notify_once

        notify_once(db, NotificationType.CARGO_DELAYED, Severity.WARNING, "LOGISTICS_OFFICER", "Shipment", ship.id, f"Shipment {ship.id} DELAYED @ {ship.current_location}: {reason or 'no reason given'}")
    db.commit()
    db.refresh(ship)
    return ship


def create_container(db: Session, ship: Shipment, code: str | None, actor_id: str) -> Container:
    code = code or f"CNT-{ship.id[:8].upper()}-{db.query(Container).filter(Container.shipment_id == ship.id).count() + 1:02d}"
    if db.query(Container).filter(Container.code == code).first():
        raise HTTPException(status_code=400, detail="container code already exists")
    container = Container(shipment_id=ship.id, code=code, location=ship.current_location)
    db.add(container)
    db.flush()
    _audit(db, actor_id, AuditAction.CREATE, "Container", container.id, new=code)
    db.commit()
    db.refresh(container)
    return container


def create_package(db: Session, container: Container, ship: Shipment, description: str, weight_kg: float, actor_id: str) -> Package:
    pid = next_package_id(db, ship.expedition_id)
    pkg = Package(
        id=pid,
        container_id=container.id,
        shipment_id=ship.id,
        description=description,
        weight_kg=weight_kg,
        status=CargoStatus.DRAFT,
        location=ship.current_location,
        qr_code=make_qr_b64(f"POLARIS:{pid}"),
    )
    db.add(pkg)
    db.flush()
    _audit(db, actor_id, AuditAction.CREATE, "Package", pkg.id, new="DRAFT")
    db.commit()
    db.refresh(pkg)
    return pkg


def add_item(db: Session, pkg: Package, name: str, quantity: float, unit: str, category: str, actor_id: str) -> CargoItem:
    item = CargoItem(package_id=pkg.id, name=name, quantity=quantity, unit=unit, category=category)
    db.add(item)
    db.flush()
    _audit(db, actor_id, AuditAction.CREATE, "CargoItem", item.id, new=f"{name} x{quantity}{unit} in {pkg.id}")
    db.commit()
    db.refresh(item)
    return item


def transition_package(db: Session, pkg: Package, to_status: CargoStatus, actor_id: str, reason: str = "", location: str | None = None) -> tuple[Package, str]:
    old = _status_val(pkg.status)
    new = _status_val(to_status)
    if not allowed_cargo_transition(old, new):
        raise HTTPException(status_code=409, detail=f"illegal cargo transition {old} -> {new}")
    pkg.status = to_status
    if location:
        pkg.location = location
    _audit(db, actor_id, AuditAction.STATUS_TRANSITION, "Package", pkg.id, old=old, new=new, reason=reason)
    if new == "DELAYED":
        from app.models.notification import NotificationType, Severity
        from app.services.notification_service import notify_once

        notify_once(db, NotificationType.CARGO_DELAYED, Severity.WARNING, "LOGISTICS_OFFICER", "Package", pkg.id, f"Package {pkg.id} DELAYED @ {pkg.location}: {reason or 'no reason given'}")
    db.commit()
    db.refresh(pkg)
    return pkg, old


def resolve_package_id(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("POLARIS:"):
        return raw.split("POLARIS:", 1)[1].strip()
    return raw


# ---- compliance documents (templated PDF, reportlab) ----

DOC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "generated_docs")


def generate_document(db: Session, ship: Shipment, doc_type: DocType, actor_id: str) -> Document:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    os.makedirs(DOC_DIR, exist_ok=True)
    containers = db.query(Container).filter(Container.shipment_id == ship.id).all()
    packages = db.query(Package).filter(Package.shipment_id == ship.id).all()
    items: list[CargoItem] = []
    for pkg in packages:
        items.extend(db.query(CargoItem).filter(CargoItem.package_id == pkg.id).all())

    fname = f"{ship.id}_{doc_type.value}.pdf"
    fpath = os.path.join(DOC_DIR, fname)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"POLARIS — {doc_type.value} (SYNTHETIC_DEMO)", styles["Title"]),
        Spacer(1, 6 * mm),
        Paragraph(f"Shipment {ship.id} | Expedition {ship.expedition_id} | {ship.origin} → {ship.destination} | Status {ship.status.value if hasattr(ship.status, 'value') else ship.status}", styles["Normal"]),
        Spacer(1, 4 * mm),
    ]
    rows = [["Package", "Description", "Item", "Qty", "Unit", "Category"]]
    for pkg in packages:
        pkg_items = [i for i in items if i.package_id == pkg.id] or [None]
        for it in pkg_items:
            rows.append([pkg.id, (pkg.description or "")[:40], it.name if it else "—", str(it.quantity) if it else "—", it.unit if it else "—", it.category if it else "—"])
    if len(rows) == 1:
        rows.append(["—", "no packages yet", "—", "—", "—", "—"])
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "grey"), ("BACKGROUND", (0, 0), (-1, 0), "lightgrey")]))
    story += [table, Spacer(1, 6 * mm), Paragraph("Generated template — not freeform LLM text. Mirrors NCPOR declaration layout.", styles["Italic"])]
    SimpleDocTemplate(fpath, pagesize=A4).build(story)

    doc = Document(shipment_id=ship.id, package_id=None, doc_type=doc_type, status=DocStatus.GENERATED, pdf_path=os.path.abspath(fpath))
    db.add(doc)
    db.flush()
    _audit(db, actor_id, AuditAction.CREATE, "Document", doc.id, new=f"{doc_type.value} for {ship.id}")
    db.commit()
    db.refresh(doc)
    return doc
