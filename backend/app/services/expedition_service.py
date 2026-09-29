from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditEvent
from app.models.expedition import Expedition, check_transition
from app.models.station import Station
from app.schemas.expedition import ExpeditionCreate, ExpeditionUpdate


def resolve_station(db: Session, ref: str) -> Station:
    station = db.query(Station).filter((Station.id == ref) | (Station.code == ref.upper())).first()
    if not station:
        raise HTTPException(status_code=400, detail=f"unknown station {ref} (use BHARATI|MAITRI|HIMADRI)")
    return station


def create_expedition(db: Session, body: ExpeditionCreate, actor_id: str) -> Expedition:
    if db.query(Expedition).filter(Expedition.id == body.id).first():
        raise HTTPException(status_code=400, detail="expedition id already exists")
    station = resolve_station(db, body.primary_station_id)
    exp = Expedition(
        id=body.id,
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
        primary_station_id=station.id,
        mission_type=body.mission_type,
        description=body.description,
        source=body.source,
    )
    db.add(exp)
    db.flush()
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.CREATE, entity_type="Expedition", entity_id=exp.id, new_value="DRAFT", source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(exp)
    return exp


def patch_expedition(db: Session, exp: Expedition, body: ExpeditionUpdate, actor_id: str) -> Expedition:
    data = body.model_dump(exclude_unset=True)
    if "primary_station_id" in data and data["primary_station_id"]:
        exp.primary_station_id = resolve_station(db, data.pop("primary_station_id")).id
    if "status" in data and data["status"] is not None:
        new = data["status"].value if hasattr(data["status"], "value") else str(data["status"])
        old = exp.status.value if hasattr(exp.status, "value") else str(exp.status)
        if new != old:
            if not check_transition(old, new):
                raise HTTPException(status_code=409, detail=f"illegal expedition transition {old} -> {new}")
            db.add(AuditEvent(actor_id=actor_id, action=AuditAction.STATUS_TRANSITION, entity_type="Expedition", entity_id=exp.id, old_value=old, new_value=new, source="SYNTHETIC_DEMO"))
            exp.status = data.pop("status")
    for key, value in data.items():
        if key == "status":
            continue
        setattr(exp, key, value)
    db.commit()
    db.refresh(exp)
    return exp
