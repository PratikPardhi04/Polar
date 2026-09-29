import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.mission import FieldMission, FieldMissionMember
from app.models.personnel import Personnel
from app.models.user import Role, User
from app.schemas.mission import (
    GoNoGoResponse,
    MemberAdd,
    MemberResponse,
    MissionCreate,
    MissionResponse,
    MissionStatusUpdate,
    MissionUpdate,
)
from app.services.mission_service import create_mission, patch_details, run_go_no_go, transition_mission

router = APIRouter(prefix="/api/v1/field-missions", tags=["field-missions"])

_write = require_role(Role.ADMIN, Role.EXPEDITION_LEADER, Role.FIELD_LEADER)


def _out(m: FieldMission) -> MissionResponse:
    return MissionResponse(
        id=m.id,
        expedition_id=m.expedition_id,
        objective=m.objective or "",
        leader_id=m.leader_id,
        vehicle_id=m.vehicle_id,
        equipment_ids=json.loads(m.equipment_ids or "[]"),
        start=m.start,
        expected_return=m.expected_return,
        route=m.route or "",
        check_in_interval_minutes=m.check_in_interval_minutes,
        grace_minutes=m.grace_minutes or 15,
        emergency_kit=bool(m.emergency_kit),
        emergency_plan=m.emergency_plan or "",
        status=m.status,
    )


def _get(db: Session, mid: str) -> FieldMission:
    m = db.query(FieldMission).filter(FieldMission.id == mid).first()
    if not m:
        raise HTTPException(status_code=404, detail="mission not found")
    return m


@router.post("", response_model=MissionResponse, status_code=201)
def create(body: MissionCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return _out(create_mission(db, body, actor_id=user.id))


@router.get("", response_model=list[MissionResponse])
def list_all(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_out(m) for m in db.query(FieldMission).order_by(FieldMission.id).all()]


@router.get("/{mid}", response_model=MissionResponse)
def get_one(mid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _out(_get(db, mid))


@router.patch("/{mid}", response_model=MissionResponse)
def patch(mid: str, body: MissionUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return _out(patch_details(db, _get(db, mid), body))


@router.post("/{mid}/members", response_model=MemberResponse, status_code=201)
def add_member(mid: str, body: MemberAdd, db: Session = Depends(get_db), user: User = Depends(_write)):
    m = _get(db, mid)
    if not db.query(Personnel).filter(Personnel.id == body.personnel_id).first():
        raise HTTPException(status_code=400, detail="unknown personnel_id")
    if db.query(FieldMissionMember).filter(FieldMissionMember.mission_id == mid, FieldMissionMember.personnel_id == body.personnel_id).first():
        raise HTTPException(status_code=400, detail="already a team member")
    mm = FieldMissionMember(mission_id=m.id, personnel_id=body.personnel_id, role=body.role)
    db.add(mm)
    db.commit()
    db.refresh(mm)
    return mm


@router.get("/{mid}/members", response_model=list[MemberResponse])
def list_members(mid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    _get(db, mid)
    return db.query(FieldMissionMember).filter(FieldMissionMember.mission_id == mid).all()


@router.post("/{mid}/go-no-go", response_model=GoNoGoResponse)
def go_no_go(mid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return run_go_no_go(db, _get(db, mid))


@router.patch("/{mid}/status", response_model=MissionResponse)
def set_status(mid: str, body: MissionStatusUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    m = _get(db, mid)
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    return _out(transition_mission(db, m, body.to_status, actor_id=user.id, actor_role=role, override_reason=body.override_reason))
