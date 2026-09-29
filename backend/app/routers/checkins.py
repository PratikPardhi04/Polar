import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.checkin import FieldCheckIn, MissionComms
from app.models.user import Role, User
from app.services.checkin_service import advance_checkins, post_comms, submit_check_in

router = APIRouter(prefix="/api/v1", tags=["check-ins"])

_ops = require_role(Role.ADMIN, Role.EXPEDITION_LEADER, Role.FIELD_LEADER)


class CheckInBody(BaseModel):
    note: str = ""
    location: str = ""


class CheckInResponse(BaseModel):
    id: str
    mission_id: str
    due_at: str
    status: str
    note: str
    location: str

    model_config = {"from_attributes": False}


class CommsBody(BaseModel):
    message: str


class CommsResponse(BaseModel):
    id: str
    mission_id: str
    author: str
    message: str
    created_at: str | None = None

    model_config = {"from_attributes": False}


def _ci_out(ci: FieldCheckIn) -> CheckInResponse:
    st = ci.status.value if hasattr(ci.status, "value") else str(ci.status)
    return CheckInResponse(id=ci.id, mission_id=ci.mission_id, due_at=ci.due_at.isoformat() if ci.due_at else "", status=st, note=ci.note or "", location=ci.location or "")


@router.post("/field-missions/{mid}/check-in", response_model=CheckInResponse, status_code=201)
def check_in(mid: str, body: CheckInBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _ci_out(submit_check_in(db, mid, actor_id=user.id, note=body.note, location=body.location))


@router.get("/field-missions/{mid}/check-ins", response_model=list[CheckInResponse])
def list_checkins(mid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_ci_out(c) for c in db.query(FieldCheckIn).filter(FieldCheckIn.mission_id == mid).order_by(FieldCheckIn.due_at).all()]


@router.post("/check-ins/advance")
def advance(db: Session = Depends(get_db), user: User = Depends(_ops)):
    _ = user
    return advance_checkins(db)


@router.post("/check-ins/advance-cron")
def advance_cron(cron_secret: str = Query(default=""), db: Session = Depends(get_db)):
    """Automation trigger for serverless hosts (Vercel Cron). Authorized by a
    shared secret, not a user token — set CRON_SECRET env on both sides."""
    expected = os.getenv("CRON_SECRET", "")
    if not expected or cron_secret != expected:
        raise HTTPException(status_code=403, detail="bad cron secret")
    return advance_checkins(db)


@router.post("/field-missions/{mid}/comms", response_model=CommsResponse, status_code=201)
def comms_post(mid: str, body: CommsBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = post_comms(db, mid, author=user.full_name or user.email, message=body.message)
    return CommsResponse(id=row.id, mission_id=row.mission_id, author=row.author, message=row.message, created_at=str(row.created_at) if row.created_at else None)


@router.get("/field-missions/{mid}/comms", response_model=list[CommsResponse])
def comms_list(mid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(MissionComms).filter(MissionComms.mission_id == mid).order_by(MissionComms.created_at).all()
    return [CommsResponse(id=r.id, mission_id=r.mission_id, author=r.author, message=r.message, created_at=str(r.created_at) if r.created_at else None) for r in rows]
