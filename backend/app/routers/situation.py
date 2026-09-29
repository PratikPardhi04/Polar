import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.situation import SituationReport
from app.models.user import Role, User
from app.services.situation_service import build_draft, publish


def _sval(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


class GenerateBody(BaseModel):
    expedition_id: str
    report_date: date


class ReportResponse(BaseModel):
    id: str
    expedition_id: str
    report_date: date
    sections: dict
    status: str
    created_by: str | None
    published_by: str | None

    model_config = {"from_attributes": False}


def _out(r: SituationReport) -> ReportResponse:
    try:
        sections = json.loads(r.sections or "{}")
    except ValueError:
        sections = {}
    return ReportResponse(
        id=r.id, expedition_id=r.expedition_id, report_date=r.report_date, sections=sections,
        status=_sval(r.status), created_by=r.created_by, published_by=r.published_by,
    )


generate_router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
reports_router = APIRouter(prefix="/api/v1/situation-reports", tags=["situation-reports"])

_publish = require_role(Role.STATION_LEADER, Role.EXPEDITION_LEADER, Role.ADMIN)


@generate_router.post("/situation-report/generate", response_model=ReportResponse, status_code=201)
def generate(body: GenerateBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Drafts a Daily Situation Report. ALWAYS DRAFT — publishing is a separate human step."""
    return _out(build_draft(db, body.expedition_id, body.report_date, actor_id=user.id))


@reports_router.get("", response_model=list[ReportResponse])
def list_all(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    expedition_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    q = db.query(SituationReport).order_by(SituationReport.report_date.desc())
    if expedition_id:
        q = q.filter(SituationReport.expedition_id == expedition_id)
    if status:
        q = q.filter(SituationReport.status == status)
    return [_out(r) for r in q.all()]


@reports_router.get("/{rep_id}", response_model=ReportResponse)
def get_one(rep_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rep = db.query(SituationReport).filter(SituationReport.id == rep_id).first()
    if not rep:
        raise HTTPException(status_code=404, detail="report not found")
    return _out(rep)


@reports_router.post("/{rep_id}/publish", response_model=ReportResponse)
def publish_report(rep_id: str, db: Session = Depends(get_db), user: User = Depends(_publish)):
    return _out(publish(db, rep_id, actor_id=user.id))
