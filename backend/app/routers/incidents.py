from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.incident import Incident
from app.models.user import Role, User
from app.schemas.incident import IncidentCreate, IncidentDetail, IncidentResponse, IncidentStatusUpdate, IncidentUpdate, ResourceMatch
from app.services.incident_service import build_detail, create_incident, match_resources, patch_incident, transition_incident

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

_write = require_role(Role.ADMIN, Role.EMERGENCY_COORDINATOR, Role.EXPEDITION_LEADER, Role.FIELD_LEADER, Role.STATION_LEADER)


@router.post("", response_model=IncidentResponse, status_code=201)
def create(body: IncidentCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return create_incident(db, body, actor_id=user.id)


@router.get("", response_model=list[IncidentResponse])
def list_all(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    status: str | None = Query(default=None),
    incident_type: str | None = Query(default=None),
    mission_id: str | None = Query(default=None),
):
    q = db.query(Incident).order_by(Incident.created_at.desc())
    if status:
        q = q.filter(Incident.status == status)
    if incident_type:
        q = q.filter(Incident.incident_type == incident_type)
    if mission_id:
        q = q.filter(Incident.mission_id == mission_id)
    return q.all()


@router.get("/{inc_id}", response_model=IncidentDetail)
def get_detail(inc_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    inc = db.query(Incident).filter(Incident.id == inc_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")
    return build_detail(db, inc)


@router.patch("/{inc_id}", response_model=IncidentResponse)
def patch(inc_id: str, body: IncidentUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    inc = db.query(Incident).filter(Incident.id == inc_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")
    return patch_incident(db, inc, body)


@router.patch("/{inc_id}/status", response_model=IncidentResponse)
def set_status(inc_id: str, body: IncidentStatusUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    inc = db.query(Incident).filter(Incident.id == inc_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")
    return transition_incident(db, inc, body.to_status, actor_id=user.id, reason=body.reason)


@router.get("/{inc_id}/resources", response_model=ResourceMatch)
def resources(inc_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    inc = db.query(Incident).filter(Incident.id == inc_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")
    return match_resources(db, inc)
