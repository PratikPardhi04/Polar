import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.audit import AuditEvent
from app.models.user import User, UserSession
from app.models.user import User as UserModel

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditResponse(BaseModel):
    id: str
    created_at: str | None
    actor_id: str | None
    actor_email: str | None = None
    action: str
    entity_type: str
    entity_id: str
    old_value: str | None = None
    new_value: str | None = None
    reason: str | None = None
    source: str

    model_config = {"from_attributes": False}


class SessionResponse(BaseModel):
    id: str
    user_id: str
    user_email: str | None = None
    role: str
    login_at: str | None
    ip_address: str
    logout_at: str | None

    model_config = {"from_attributes": False}


def _filtered(
    db: Session,
    entity_type: str | None,
    entity_id: str | None,
    actor: str | None,
    action: str | None,
    since: str | None,
    until: str | None,
    search: str | None,
):
    q = db.query(AuditEvent)
    if entity_type:
        q = q.filter(AuditEvent.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditEvent.entity_id == entity_id)
    if action:
        q = q.filter(AuditEvent.action == action)
    if actor:
        users = db.query(UserModel).filter(UserModel.email.ilike(f"%{actor}%")).all()
        ids = [u.id for u in users]
        cond = AuditEvent.actor_id.in_(ids) if ids else AuditEvent.actor_id == actor
        q = q.filter(or_(cond, AuditEvent.actor_id.ilike(f"%{actor}%")))
    if since:
        q = q.filter(AuditEvent.created_at >= datetime.fromisoformat(since))
    if until:
        q = q.filter(AuditEvent.created_at <= datetime.fromisoformat(until))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(AuditEvent.entity_id.ilike(like), AuditEvent.entity_type.ilike(like), AuditEvent.old_value.ilike(like), AuditEvent.new_value.ilike(like), AuditEvent.reason.ilike(like)))
    return q.order_by(AuditEvent.created_at.desc())


def _out(db: Session, e: AuditEvent) -> AuditResponse:
    email = None
    if e.actor_id:
        u = db.query(UserModel).filter(UserModel.id == e.actor_id).first()
        email = u.email if u else None
    return AuditResponse(
        id=e.id, created_at=str(e.created_at) if e.created_at else None, actor_id=e.actor_id, actor_email=email,
        action=e.action, entity_type=e.entity_type, entity_id=e.entity_id,
        old_value=e.old_value, new_value=e.new_value, reason=e.reason, source=e.source,
    )


@router.get("/events", response_model=list[AuditResponse])
def list_events(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    actor: str | None = Query(default=None, description="actor email fragment or id"),
    action: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    search: str | None = Query(default=None, description='free text, e.g. "BX-0042"'),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return [_out(db, e) for e in _filtered(db, entity_type, entity_id, actor, action, since, until, search).offset(offset).limit(limit).all()]


@router.get("/events/export")
def export_events(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    rows = _filtered(db, entity_type, entity_id, actor, action, since, until, search).limit(5000).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "created_at", "actor_id", "actor_email", "action", "entity_type", "entity_id", "old_value", "new_value", "reason", "source"])
    for e in rows:
        o = _out(db, e)
        w.writerow([o.id, o.created_at, o.actor_id, o.actor_email, o.action, o.entity_type, o.entity_id, o.old_value, o.new_value, o.reason, o.source])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=polaris_audit_export.csv"})


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(db: Session = Depends(get_db), _: User = Depends(get_current_user), limit: int = Query(default=100, ge=1, le=500)):
    out = []
    for s in db.query(UserSession).order_by(UserSession.login_at.desc()).limit(limit).all():
        u = db.query(UserModel).filter(UserModel.id == s.user_id).first()
        out.append(SessionResponse(id=s.id, user_id=s.user_id, user_email=u.email if u else None, role=s.role, login_at=str(s.login_at) if s.login_at else None, ip_address=s.ip_address, logout_at=str(s.logout_at) if s.logout_at else None))
    return out
