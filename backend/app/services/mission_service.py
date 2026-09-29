import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.asset import Asset, Vehicle
from app.models.audit import AuditAction, AuditEvent
from app.models.expedition import Expedition
from app.models.mission import ALLOWED_MISSION_TRANSITIONS, READY_STATES, FieldMission, FieldMissionMember, MissionStatus
from app.models.personnel import Personnel
from app.models.weather import WeatherSnapshot
from app.schemas.mission import GoNoGoCheck, GoNoGoResponse, MissionCreate, MissionUpdate
from app.services.weather_service import evaluate_weather


def _sval(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


def _audit(db: Session, actor_id: str | None, action: str, entity: str, eid: str, old: str | None = None, new: str | None = None, reason: str = ""):
    db.add(AuditEvent(actor_id=actor_id, action=action, entity_type=entity, entity_id=eid, old_value=old, new_value=new, reason=reason, source="SYNTHETIC_DEMO"))


def _equipment_ids(m: FieldMission) -> list[str]:
    try:
        return json.loads(m.equipment_ids or "[]")
    except (ValueError, TypeError):
        return []


def next_mission_id(db: Session) -> str:
    n = db.query(FieldMission).count() + 1
    while db.query(FieldMission).filter(FieldMission.id == f"FM-{n:03d}").first():
        n += 1
    return f"FM-{n:03d}"


def create_mission(db: Session, body: MissionCreate, actor_id: str) -> FieldMission:
    if not db.query(Expedition).filter(Expedition.id == body.expedition_id).first():
        raise HTTPException(status_code=400, detail=f"unknown expedition {body.expedition_id}")
    mid = body.id or next_mission_id(db)
    if db.query(FieldMission).filter(FieldMission.id == mid).first():
        raise HTTPException(status_code=400, detail="mission id already exists")
    data = body.model_dump(exclude={"id", "equipment_ids"})
    m = FieldMission(id=mid, equipment_ids=json.dumps(body.equipment_ids), **{k: v for k, v in data.items()})
    db.add(m)
    db.flush()
    _audit(db, actor_id, AuditAction.CREATE, "FieldMission", m.id, new="DRAFT")
    db.commit()
    db.refresh(m)
    return m


def run_go_no_go(db: Session, m: FieldMission) -> GoNoGoResponse:
    """Deterministic checks in fixed order. No LLM, no side effects."""
    checks: list[GoNoGoCheck] = []

    # 1. personnel ready
    members = db.query(FieldMissionMember).filter(FieldMissionMember.mission_id == m.id).all()
    if m.leader_id and not any(mm.personnel_id == m.leader_id for mm in members):
        members = members + [FieldMissionMember(mission_id=m.id, personnel_id=m.leader_id, role="LEADER")]
    unready: list[str] = []
    for mm in members:
        p = db.query(Personnel).filter(Personnel.id == mm.personnel_id).first()
        state = _sval(p.current_readiness) if p else "UNKNOWN"
        if not p or state not in READY_STATES:
            unready.append(f"{p.full_name if p else mm.personnel_id} ({state})")
    checks.append(GoNoGoCheck(name="personnel_ready", passed=not unready and len(members) > 0, detail="team ready" if members and not unready else (f"not ready: {', '.join(unready)}" if unready else "no team assigned")))

    # 2. equipment ready
    bad_eq: list[str] = []
    for aid in _equipment_ids(m):
        a = db.query(Asset).filter(Asset.id == aid).first()
        st = _sval(a.status) if a else "UNKNOWN"
        if not a or st != "IN_SERVICE":
            bad_eq.append(f"{a.name if a else aid} ({st})")
    checks.append(GoNoGoCheck(name="equipment_ready", passed=not bad_eq, detail="equipment IN_SERVICE" if not bad_eq else f"not ready: {', '.join(bad_eq)}"))

    # 3. vehicle ready
    if not m.vehicle_id:
        checks.append(GoNoGoCheck(name="vehicle_ready", passed=False, detail="no vehicle assigned"))
    else:
        v = db.query(Vehicle).filter(Vehicle.id == m.vehicle_id).first()
        a = db.query(Asset).filter(Asset.id == v.asset_id).first() if v else None
        st = _sval(a.status) if a else "UNKNOWN"
        checks.append(GoNoGoCheck(name="vehicle_ready", passed=bool(a) and st == "IN_SERVICE", detail=f"vehicle {st}" if a else "unknown vehicle"))

    # 4. weather acceptable — real thresholds over the latest WeatherSnapshot (4.2)
    from app.models.station import Station

    exp = db.query(Expedition).filter(Expedition.id == m.expedition_id).first()
    station_id = exp.primary_station_id if exp else None
    station_code = "BHARATI"
    if station_id:
        st = db.query(Station).filter(Station.id == station_id).first()
        if st:
            station_code = st.code
    snap = None
    if station_id:
        snap = (
            db.query(WeatherSnapshot)
            .filter(WeatherSnapshot.station_id == station_id)
            .order_by(WeatherSnapshot.fetched_at.desc())
            .first()
        )
    if snap is None:
        checks.append(GoNoGoCheck(name="weather_acceptable", passed=True, detail=f"no snapshot yet — GET /api/v1/weather/{station_code} for live data"))
    else:
        passed, detail = evaluate_weather(snap)
        checks.append(GoNoGoCheck(name="weather_acceptable", passed=passed, detail=f"{detail} (snapshot {snap.fetched_at})"))

    # 5. emergency plan present
    kit_ok = bool(m.emergency_kit) and bool((m.emergency_plan or "").strip())
    checks.append(GoNoGoCheck(name="emergency_plan_present", passed=kit_ok, detail="kit + plan on file" if kit_ok else "emergency kit flag and written plan both required"))

    all_passed = all(c.passed for c in checks)
    return GoNoGoResponse(all_passed=all_passed, deploy_allowed=all_passed, checks=checks)


OVERRIDE_ROLES = {"FIELD_LEADER", "EXPEDITION_LEADER", "ADMIN"}


def transition_mission(db: Session, m: FieldMission, to_status: MissionStatus, actor_id: str, actor_role: str, override_reason: str = "") -> FieldMission:
    old, new = _sval(m.status), _sval(to_status)
    if new != old:
        if new not in ALLOWED_MISSION_TRANSITIONS.get(old, set()):
            raise HTTPException(status_code=409, detail=f"illegal mission transition {old} -> {new}")
        if new == "DEPLOYED":
            verdict = run_go_no_go(db, m)
            if not verdict.all_passed:
                if not override_reason.strip() or (actor_role or "") not in OVERRIDE_ROLES:
                    failed = ", ".join(c.name for c in verdict.checks if not c.passed)
                    raise HTTPException(status_code=409, detail=f"go/no-go FAILED ({failed}); Field Leader override with reason required")
                _audit(db, actor_id, AuditAction.OVERRIDE, "FieldMission", m.id, old=old, new=new, reason=override_reason)
        _audit(db, actor_id, AuditAction.STATUS_TRANSITION, "FieldMission", m.id, old=old, new=new, reason=override_reason)
        m.status = to_status
        db.commit()
        db.refresh(m)
    return m


def patch_details(db: Session, m: FieldMission, body: MissionUpdate) -> FieldMission:
    data = body.model_dump(exclude_unset=True)
    if "equipment_ids" in data and data["equipment_ids"] is not None:
        m.equipment_ids = json.dumps(data.pop("equipment_ids"))
    for key, value in data.items():
        setattr(m, key, value)
    db.commit()
    db.refresh(m)
    return m
