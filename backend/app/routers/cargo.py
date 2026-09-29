from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.cargo import Container, Document, Package, Shipment
from app.models.user import Role, User
from app.schemas.cargo import (
    ContainerCreate,
    ContainerResponse,
    DocumentGenerate,
    DocumentResponse,
    ItemCreate,
    ItemResponse,
    PackageCreate,
    PackageResponse,
    ScanRequest,
    ScanResponse,
    ShipmentCreate,
    ShipmentResponse,
    StatusUpdate,
)
from app.services.cargo_service import (
    add_item,
    create_container,
    create_package,
    create_shipment,
    generate_document,
    resolve_package_id,
    transition_package,
    transition_shipment,
)

router = APIRouter(prefix="/api/v1", tags=["cargo"])

_write = require_role(Role.ADMIN, Role.EXPEDITION_LEADER, Role.LOGISTICS_OFFICER)


def _get_ship(db: Session, ship_id: str) -> Shipment:
    ship = db.query(Shipment).filter(Shipment.id == ship_id).first()
    if not ship:
        raise HTTPException(status_code=404, detail="shipment not found")
    return ship


@router.post("/shipments", response_model=ShipmentResponse, status_code=201)
def create_ship(body: ShipmentCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return create_shipment(db, body.expedition_id, body.origin, body.destination, actor_id=user.id)


@router.get("/shipments", response_model=list[ShipmentResponse])
def list_ships(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Shipment).order_by(Shipment.created_at).all()


@router.get("/shipments/{ship_id}", response_model=ShipmentResponse)
def get_ship(ship_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _get_ship(db, ship_id)


@router.patch("/shipments/{ship_id}/status", response_model=ShipmentResponse)
def ship_status(ship_id: str, body: StatusUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return transition_shipment(db, _get_ship(db, ship_id), body.to_status, actor_id=user.id, reason=body.reason, location=body.location)


@router.post("/shipments/{ship_id}/containers", response_model=ContainerResponse, status_code=201)
def add_container(ship_id: str, body: ContainerCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return create_container(db, _get_ship(db, ship_id), body.code, actor_id=user.id)


@router.get("/shipments/{ship_id}/containers", response_model=list[ContainerResponse])
def list_containers(ship_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    _get_ship(db, ship_id)
    return db.query(Container).filter(Container.shipment_id == ship_id).order_by(Container.code).all()


@router.get("/shipments/{ship_id}/packages", response_model=list[PackageResponse])
def list_packages(ship_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    _get_ship(db, ship_id)
    return db.query(Package).filter(Package.shipment_id == ship_id).order_by(Package.id).all()


@router.post("/containers/{container_id}/packages", response_model=PackageResponse, status_code=201)
def add_package(container_id: str, body: PackageCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    container = db.query(Container).filter(Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="container not found")
    ship = _get_ship(db, container.shipment_id)
    return create_package(db, container, ship, body.description, body.weight_kg, actor_id=user.id)


@router.post("/packages/{package_id}/items", response_model=ItemResponse, status_code=201)
def add_pkg_item(package_id: str, body: ItemCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    pkg = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="package not found")
    return add_item(db, pkg, body.name, body.quantity, body.unit, body.category, actor_id=user.id)


@router.get("/packages/{package_id}", response_model=PackageResponse)
def get_package(package_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    pkg = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="package not found")
    return pkg


@router.patch("/packages/{package_id}/status", response_model=PackageResponse)
def package_status(package_id: str, body: StatusUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    pkg = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="package not found")
    pkg, _ = transition_package(db, pkg, body.to_status, actor_id=user.id, reason=body.reason, location=body.location)
    return pkg


@router.post("/scan", response_model=ScanResponse)
def scan(body: ScanRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pid = resolve_package_id(body.package_id)
    pkg = db.query(Package).filter(Package.id == pid).first()
    if not pkg:
        raise HTTPException(status_code=404, detail=f"package {pid} not found")
    prev = pkg.status.value if hasattr(pkg.status, "value") else str(pkg.status)
    if body.to_status is not None:
        pkg, prev = transition_package(db, pkg, body.to_status, actor_id=user.id, reason="scan", location=body.location)
    elif body.location:
        pkg.location = body.location
        db.commit()
        db.refresh(pkg)
    detail = f"{pkg.id} | {prev} -> {pkg.status.value if hasattr(pkg.status, 'value') else pkg.status} | loc {pkg.location}"
    return ScanResponse(package=pkg, previous_status=prev, detail=detail)


@router.post("/shipments/{ship_id}/documents/generate", response_model=DocumentResponse, status_code=201)
def gen_doc(ship_id: str, body: DocumentGenerate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return generate_document(db, _get_ship(db, ship_id), body.doc_type, actor_id=user.id)


@router.get("/shipments/{ship_id}/documents", response_model=list[DocumentResponse])
def list_docs(ship_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    _get_ship(db, ship_id)
    docs = db.query(Document).filter(Document.shipment_id == ship_id).all()
    return [DocumentResponse(id=d.id, shipment_id=d.shipment_id, package_id=d.package_id, doc_type=d.doc_type, status=d.status.value if hasattr(d.status, "value") else str(d.status), pdf_path=d.pdf_path) for d in docs]


@router.get("/documents/{doc_id}/download")
def download_doc(doc_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return FileResponse(doc.pdf_path, media_type="application/pdf", filename=f"{doc.doc_type}_synthetic.pdf")
