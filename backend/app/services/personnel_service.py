from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditEvent
from app.models.personnel import ALLOWED_TRANSITIONS, Personnel, PersonnelReadinessEvent, ReadinessState
from app.schemas.personnel import PersonnelCreate, PersonnelUpdate


def _state_val(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


def can_close_out(db: Session, personnel_id: str) -> tuple[bool, str]:
    """CLOSED_OUT gate: no open incidents + no ACTIVE field mission assignments.

    Forward-compatible: Phase 4/5 tables may not exist yet — inspected at runtime.
    """
    tables = set(inspect(db.bind if hasattr(db, "bind") else db.get_bind()).get_table_names())
    if "incidents" in tables:
        cols = {c["name"] for c in inspect(db.bind if hasattr(db, "bind") else db.get_bind()).get_columns("incidents")}
        pid_col = "personnel_id" if "personnel_id" in cols else ("person_id" if "person_id" in cols else None)
        if pid_col:
            row = db.execute(
                __import__("sqlalchemy").text(
                    f"SELECT id FROM incidents WHERE {pid_col} = :pid AND status NOT IN ('RESOLVED','CLOSED') LIMIT 1"
                ),
                {"pid": personnel_id},
            ).first()
            if row:
                return False, "person has open incidents"
    member_tables = [t for t in ("field_mission_members", "fieldmission_members", "mission_members") if t in tables]
    mission_tables = [t for t in ("field_missions", "fieldmissions", "missions") if t in tables]
    if member_tables and mission_tables:
        mt, mist = member_tables[0], mission_tables[0]
        cols_m = {c["name"] for c in inspect(db.bind if hasattr(db, "bind") else db.get_bind()).get_columns(mt)}
        pid_col = "personnel_id" if "personnel_id" in cols_m else ("person_id" if "person_id" in cols_m else None)
        if pid_col:
            row = db.execute(
                __import__("sqlalchemy").text(
                    f"SELECT m.id FROM {mist} m JOIN {mt} mm ON mm.mission_id = m.id "
                    f"WHERE mm.{pid_col} = :pid AND m.status = 'ACTIVE' LIMIT 1"
                ),
                {"pid": personnel_id},
            ).first()
            if row:
                return False, "person still assigned to an ACTIVE field mission"
    return True, ""


def create_personnel(db: Session, body: PersonnelCreate, actor_id: str) -> Personnel:
    person = Personnel(
        full_name=body.full_name,
        email=body.email.lower(),
        phone=body.phone,
        role=body.role,
        expedition_id=body.expedition_id,
        emergency_contact=body.emergency_contact,
        current_readiness=ReadinessState.NOMINATED,
    )
    db.add(person)
    db.flush()
    db.add(PersonnelReadinessEvent(personnel_id=person.id, from_state=None, to_state="NOMINATED", actor_id=actor_id, reason="nominated"))
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.CREATE, entity_type="Personnel", entity_id=person.id, new_value="NOMINATED", source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(person)
    return person


def transition_readiness(db: Session, person: Personnel, to_state: ReadinessState, actor_id: str, reason: str) -> Personnel:
    old = _state_val(person.current_readiness)
    new = _state_val(to_state)
    if new == old:
        return person
    if new not in ALLOWED_TRANSITIONS.get(old, set()):
        raise HTTPException(status_code=409, detail=f"illegal readiness transition {old} -> {new}")
    if new == "CLOSED_OUT":
        ok, why = can_close_out(db, person.id)
        if not ok:
            raise HTTPException(status_code=409, detail=f"cannot CLOSE_OUT: {why}")
    person.current_readiness = to_state
    db.add(PersonnelReadinessEvent(personnel_id=person.id, from_state=old, to_state=new, actor_id=actor_id, reason=reason))
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.STATUS_TRANSITION, entity_type="Personnel", entity_id=person.id, old_value=old, new_value=new, reason=reason, source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(person)
    return person


def update_details(db: Session, person: Personnel, body: PersonnelUpdate) -> Personnel:
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(person, key, value)
    db.commit()
    db.refresh(person)
    return person
