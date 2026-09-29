from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.audit import AuditAction, AuditEvent
from app.models.plan import PlanDraft, PlanKind, PlanStatus
from app.models.user import Role, User

router = APIRouter(prefix="/api/v1/plan-drafts", tags=["plan-drafts"])

_approve = require_role(Role.ADMIN, Role.EXPEDITION_LEADER)


class PlanCreate(BaseModel):
    title: str
    kind: PlanKind = PlanKind.GENERAL
    body: dict = {}


class PlanResponse(BaseModel):
    id: str
    title: str
    kind: PlanKind
    body: dict
    status: PlanStatus
    created_by: str | None

    model_config = {"from_attributes": False}


class PlanDecision(BaseModel):
    decision: str  # APPROVE | REJECT
    note: str = ""


def _out(p: PlanDraft) -> PlanResponse:
    import json

    try:
        body = json.loads(p.body or "{}")
    except ValueError:
        body = {"raw": p.body}
    return PlanResponse(id=p.id, title=p.title, kind=p.kind, body=body, status=p.status, created_by=p.created_by)


@router.post("", response_model=PlanResponse, status_code=201)
def create(body: PlanCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    import json

    draft = PlanDraft(title=body.title, kind=body.kind, body=json.dumps(body.body), status=PlanStatus.DRAFT, created_by=user.id)
    db.add(draft)
    db.flush()
    db.add(AuditEvent(actor_id=user.id, action=AuditAction.CREATE, entity_type="PlanDraft", entity_id=draft.id, new_value=f"DRAFT: {draft.title}", source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(draft)
    return _out(draft)


@router.get("", response_model=list[PlanResponse])
def list_all(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_out(p) for p in db.query(PlanDraft).order_by(PlanDraft.created_at.desc()).all()]


@router.post("/{pid}/decide", response_model=PlanResponse)
def decide(pid: str, body: PlanDecision, db: Session = Depends(get_db), user: User = Depends(_approve)):
    if body.decision not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=400, detail="decision must be APPROVE or REJECT")
    draft = db.query(PlanDraft).filter(PlanDraft.id == pid).first()
    if not draft:
        raise HTTPException(status_code=404, detail="plan draft not found")
    current = draft.status.value if hasattr(draft.status, "value") else str(draft.status)
    if current != "DRAFT":
        raise HTTPException(status_code=409, detail=f"already decided ({current})")
    draft.status = PlanStatus.APPROVED if body.decision == "APPROVE" else PlanStatus.REJECTED
    db.add(AuditEvent(actor_id=user.id, action=AuditAction.APPROVE, entity_type="PlanDraft", entity_id=draft.id, new_value=body.decision, reason=body.note, source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(draft)
    return _out(draft)
