from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.personnel import Personnel, PersonnelReadinessEvent
from app.models.user import Role, User
from app.schemas.personnel import MovementEvent, PersonnelCreate, PersonnelResponse, PersonnelUpdate, ReadinessSummary, ReadinessTransition
from app.services.personnel_service import create_personnel, transition_readiness, update_details

router = APIRouter(prefix="/api/v1/personnel", tags=["personnel"])

_write = require_role(Role.ADMIN, Role.EXPEDITION_LEADER)


@router.post("", response_model=PersonnelResponse, status_code=201)
def create(body: PersonnelCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return create_personnel(db, body, actor_id=user.id)


@router.get("/readiness/summary", response_model=ReadinessSummary)
def readiness_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(Personnel.current_readiness, func.count()).group_by(Personnel.current_readiness).all()
    by_state = {(r[0].value if hasattr(r[0], "value") else str(r[0])): r[1] for r in rows}
    return ReadinessSummary(total=sum(by_state.values()), by_state=by_state)


@router.get("", response_model=list[PersonnelResponse])
def list_all(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    readiness: str | None = Query(default=None),
    expedition_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
):
    query = db.query(Personnel)
    if readiness:
        query = query.filter(Personnel.current_readiness == readiness)
    if expedition_id:
        query = query.filter(Personnel.expedition_id == expedition_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(func.lower(Personnel.full_name).like(like) | func.lower(Personnel.email).like(like))
    return query.order_by(Personnel.full_name).all()


@router.get("/{person_id}", response_model=PersonnelResponse)
def get_one(person_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    person = db.query(Personnel).filter(Personnel.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="personnel not found")
    return person


@router.patch("/{person_id}", response_model=PersonnelResponse)
def patch_details(person_id: str, body: PersonnelUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    person = db.query(Personnel).filter(Personnel.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="personnel not found")
    return update_details(db, person, body)


@router.patch("/{person_id}/readiness", response_model=PersonnelResponse)
def patch_readiness(person_id: str, body: ReadinessTransition, db: Session = Depends(get_db), user: User = Depends(_write)):
    person = db.query(Personnel).filter(Personnel.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="personnel not found")
    return transition_readiness(db, person, body.to_state, actor_id=user.id, reason=body.reason)


@router.get("/{person_id}/movements", response_model=list[MovementEvent])
def movements(person_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if not db.query(Personnel).filter(Personnel.id == person_id).first():
        raise HTTPException(status_code=404, detail="personnel not found")
    rows = db.query(PersonnelReadinessEvent).filter(PersonnelReadinessEvent.personnel_id == person_id).order_by(PersonnelReadinessEvent.created_at).all()
    return [MovementEvent(id=r.id, from_state=r.from_state, to_state=r.to_state, actor_id=r.actor_id, reason=r.reason or "", created_at=str(r.created_at) if r.created_at else None) for r in rows]
