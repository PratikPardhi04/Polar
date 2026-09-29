import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.mission import FieldMission
from app.models.report import MissionReport, PhaseReport
from app.models.user import Role, User
from app.services.closeout_service import close_expedition_phase, close_mission

router = APIRouter(prefix="/api/v1", tags=["closeout"])

_close = require_role(Role.ADMIN, Role.EXPEDITION_LEADER, Role.FIELD_LEADER)
_phase = require_role(Role.ADMIN, Role.EXPEDITION_LEADER)


class MissionCloseBody(BaseModel):
    closing_summary: str = ""
    outcome: str = "SUCCESS"
    vehicle_condition: str = "RETURNED"
    equipment: dict[str, str] = {}


class PhaseCloseBody(BaseModel):
    phase_name: str = ""
    summary: str = ""


def _sval(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


@router.post("/field-missions/{mid}/close", status_code=201)
def close(mid: str, body: MissionCloseBody, db: Session = Depends(get_db), user: User = Depends(_close)):
    from app.models.report import MissionOutcome

    try:
        outcome = MissionOutcome(body.outcome.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="outcome must be SUCCESS|PARTIAL|ABORTED")
    rep = close_mission(db, mid, actor_id=user.id, closing_summary=body.closing_summary, outcome=outcome, vehicle_condition=body.vehicle_condition.upper(), equipment={k: v.upper() for k, v in (body.equipment or {}).items()})
    return {"mission_id": mid, "report_id": rep.id, "status": "CLOSED"}


@router.get("/field-missions/{mid}/report")
def get_report(mid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rep = db.query(MissionReport).filter(MissionReport.mission_id == mid).first()
    if not rep:
        raise HTTPException(status_code=404, detail="no report for this mission yet")
    m = db.query(FieldMission).filter(FieldMission.id == mid).first()
    return {"mission_id": mid, "mission_status": _sval(m.status) if m else "?", "outcome": _sval(rep.outcome), "html": rep.html, "pdf_url": f"/api/v1/field-missions/{mid}/report.pdf"}


@router.get("/field-missions/{mid}/report.pdf")
def get_report_pdf(mid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rep = db.query(MissionReport).filter(MissionReport.mission_id == mid).first()
    if not rep:
        raise HTTPException(status_code=404, detail="no report for this mission yet")
    return FileResponse(rep.pdf_path, media_type="application/pdf", filename=f"{mid}_mission_report.pdf")


@router.post("/expeditions/{eid}/close-phase", status_code=201)
def close_phase(eid: str, body: PhaseCloseBody, db: Session = Depends(get_db), user: User = Depends(_phase)):
    rep = close_expedition_phase(db, eid, actor_id=user.id, phase_name=body.phase_name, summary=body.summary)
    return {"expedition_id": eid, "phase_report_id": rep.id, "pdf_url": f"/api/v1/phase-reports/{rep.id}/download"}


@router.get("/expeditions/{eid}/phase-reports")
def list_phase_reports(eid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(PhaseReport).filter(PhaseReport.expedition_id == eid).order_by(PhaseReport.created_at).all()
    return [{"id": r.id, "phase_name": r.phase_name, "summary": r.summary, "rollup": json.loads(r.rollup or "{}"), "pdf_url": f"/api/v1/phase-reports/{r.id}/download"} for r in rows]


@router.get("/phase-reports/{rid}/download")
def download_phase_report(rid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rep = db.query(PhaseReport).filter(PhaseReport.id == rid).first()
    if not rep:
        raise HTTPException(status_code=404, detail="phase report not found")
    return FileResponse(rep.pdf_path, media_type="application/pdf", filename=f"{rep.expedition_id}_{rep.phase_name}_phase_report.pdf")
