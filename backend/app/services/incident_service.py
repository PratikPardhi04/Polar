from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.asset import Asset, Vehicle
from app.models.audit import AuditAction, AuditEvent
from app.models.checkin import MissionComms
from app.models.expedition import Expedition
from app.models.incident import Incident, IncidentStatus
from app.models.mission import READY_STATES, FieldMission, FieldMissionMember
from app.models.personnel import Personnel
from app.models.station import Station
from app.models.weather import WeatherSnapshot
from app.schemas.incident import IncidentCreate, IncidentDetail, IncidentResponse, IncidentUpdate, MissionBrief, PersonBrief, ResourceMatch, VehicleBrief

ALLOWED_INCIDENT_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"ASSESSING", "CLOSED"},
    "ASSESSING": {"RESPONDING", "CLOSED"},
    "RESPONDING": {"RESOLVED", "CLOSED"},
    "RESOLVED": {"CLOSED", "RESPONDING"},
    "CLOSED": set(),
}

# "AVAILABLE" stub: ready at station, not deployed out
AVAILABLE_READINESS = {"MISSION_READY", "INDUCTED", "AT_STATION"}


def _sval(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


def _audit(db: Session, actor_id: str | None, action: str, eid: str, old: str | None = None, new: str | None = None, reason: str = ""):
    db.add(AuditEvent(actor_id=actor_id, action=action, entity_type="Incident", entity_id=eid, old_value=old, new_value=new, reason=reason, source="SYNTHETIC_DEMO"))


def create_incident(db: Session, body: IncidentCreate, actor_id: str) -> Incident:
    if body.personnel_id and not db.query(Personnel).filter(Personnel.id == body.personnel_id).first():
        raise HTTPException(status_code=400, detail="unknown personnel_id")
    if body.mission_id and not db.query(FieldMission).filter(FieldMission.id == body.mission_id).first():
        raise HTTPException(status_code=400, detail="unknown mission_id")
    inc = Incident(incident_type=body.incident_type, personnel_id=body.personnel_id, mission_id=body.mission_id, last_location=body.last_location, detail=body.detail)
    db.add(inc)
    db.flush()
    _audit(db, actor_id, AuditAction.CREATE, inc.id, new=f"{_sval(inc.incident_type)} OPEN")
    if _sval(inc.incident_type) == "MEDICAL":
        from app.services.notification_service import notify_medical

        notify_medical(db, inc.id, body.detail or body.last_location)
    db.commit()
    db.refresh(inc)
    return inc


def patch_incident(db: Session, inc: Incident, body: IncidentUpdate) -> Incident:
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(inc, key, value)
    db.commit()
    db.refresh(inc)
    return inc


def transition_incident(db: Session, inc: Incident, to_status, actor_id: str, reason: str = "") -> Incident:
    old, new = _sval(inc.status), _sval(to_status)
    if new != old:
        if new not in ALLOWED_INCIDENT_TRANSITIONS.get(old, set()):
            raise HTTPException(status_code=409, detail=f"illegal incident transition {old} -> {new}")
        inc.status = to_status
        _audit(db, actor_id, AuditAction.STATUS_TRANSITION, inc.id, old=old, new=new, reason=reason)
        db.commit()
        db.refresh(inc)
    return inc


def _person_brief(p: Personnel | None) -> PersonBrief | None:
    if not p:
        return None
    return PersonBrief(id=p.id, full_name=p.full_name, readiness=_sval(p.current_readiness))


def build_detail(db: Session, inc: Incident) -> IncidentDetail:
    person = db.query(Personnel).filter(Personnel.id == inc.personnel_id).first() if inc.personnel_id else None
    mission = db.query(FieldMission).filter(FieldMission.id == inc.mission_id).first() if inc.mission_id else None
    team: list[PersonBrief] = []
    vehicle: VehicleBrief | None = None
    weather: dict | None = None
    if mission:
        for mm in db.query(FieldMissionMember).filter(FieldMissionMember.mission_id == mission.id).all():
            b = _person_brief(db.query(Personnel).filter(Personnel.id == mm.personnel_id).first())
            if b:
                team.append(b)
        if mission.vehicle_id:
            v = db.query(Vehicle).filter(Vehicle.id == mission.vehicle_id).first()
            if v:
                a = db.query(Asset).filter(Asset.id == v.asset_id).first()
                vehicle = VehicleBrief(id=v.id, registration_number=v.registration_number, asset_status=_sval(a.status) if a else "UNKNOWN")
        exp = db.query(Expedition).filter(Expedition.id == mission.expedition_id).first()
        if exp:
            snap = db.query(WeatherSnapshot).filter(WeatherSnapshot.station_id == exp.primary_station_id).order_by(WeatherSnapshot.fetched_at.desc()).first()
            if snap:
                st = db.query(Station).filter(Station.id == snap.station_id).first()
                weather = {"station": st.code if st else "?", "condition": snap.condition, "temp_c": snap.temp_c, "wind_kph": snap.wind_kph, "fetched_at": str(snap.fetched_at)}
    comms = db.query(MissionComms).filter(MissionComms.mission_id == inc.mission_id).order_by(MissionComms.created_at.desc()).all() if inc.mission_id else []
    return IncidentDetail(
        incident=IncidentResponse.model_validate(inc),
        person=_person_brief(person),
        mission=MissionBrief(id=mission.id, objective=mission.objective or "", status=_sval(mission.status)) if mission else None,
        team=team,
        vehicle=vehicle,
        weather=weather,
        last_comms_at=str(comms[0].created_at) if comms else None,
        comms_count=len(comms),
    )


def match_resources(db: Session, inc: Incident) -> ResourceMatch:
    """Stub: same-expedition available personnel + IN_SERVICE vehicles. No real geo — stretch goal."""
    mission = db.query(FieldMission).filter(FieldMission.id == inc.mission_id).first() if inc.mission_id else None
    exp_id = mission.expedition_id if mission else None
    on_mission = {mm.personnel_id for mm in db.query(FieldMissionMember).filter(FieldMissionMember.mission_id == inc.mission_id).all()} if inc.mission_id else set()
    q = db.query(Personnel).filter(Personnel.current_readiness.in_(list(AVAILABLE_READINESS)))
    if exp_id:
        q = q.filter((Personnel.expedition_id == exp_id) | (Personnel.expedition_id.is_(None)))
    personnel = [_person_brief(p) for p in q.order_by(Personnel.full_name).all() if p.id not in on_mission and (not inc.personnel_id or p.id != inc.personnel_id)]
    vehicles = []
    for v in db.query(Vehicle).all():
        a = db.query(Asset).filter(Asset.id == v.asset_id).first()
        if a and _sval(a.status) == "IN_SERVICE" and (not mission or not mission.vehicle_id or v.id != mission.vehicle_id):
            vehicles.append(VehicleBrief(id=v.id, registration_number=v.registration_number, asset_status="IN_SERVICE"))
    return ResourceMatch(personnel=[p for p in personnel if p], vehicles=vehicles)
