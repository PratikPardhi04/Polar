from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditEvent
from app.models.checkin import ESCALATION_LADDER, CheckInStatus, FieldCheckIn, MissionComms
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.mission import FieldMission


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sval(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


def _mission(db: Session, mid: str) -> FieldMission:
    m = db.query(FieldMission).filter(FieldMission.id == mid).first()
    if not m:
        raise HTTPException(status_code=404, detail="mission not found")
    return m


def submit_check_in(db: Session, mid: str, actor_id: str, note: str = "", location: str = "") -> FieldCheckIn:
    """Mark the latest open check-in CHECKED_IN and schedule the next DUE one."""
    m = _mission(db, mid)
    if _sval(m.status) not in ("DEPLOYED", "ACTIVE"):
        raise HTTPException(status_code=409, detail="check-ins only run on DEPLOYED/ACTIVE missions")
    now = _now()
    current = (
        db.query(FieldCheckIn)
        .filter(FieldCheckIn.mission_id == mid, FieldCheckIn.status != CheckInStatus.CHECKED_IN)
        .order_by(FieldCheckIn.due_at.desc())
        .first()
    )
    if current:
        current.status = CheckInStatus.CHECKED_IN
        current.checked_in_at = now
        if note:
            current.note = note
        if location:
            current.location = location
    nxt = FieldCheckIn(mission_id=mid, due_at=now + timedelta(minutes=m.check_in_interval_minutes or 60), status=CheckInStatus.DUE)
    db.add(nxt)
    db.flush()
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.STATUS_TRANSITION, entity_type="FieldCheckIn", entity_id=nxt.id, new_value=f"DUE @ {nxt.due_at.isoformat()}", reason=note, source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(nxt)
    return nxt


def _ensure_draft_incident(db: Session, ci: FieldCheckIn, m: FieldMission):
    """On MISSED_CHECK_IN: draft MISSING_PERSON incident. Never an SOS (sos_flag stays False)."""
    if db.query(Incident).filter(Incident.check_in_id == ci.id).first():
        return
    db.add(
        Incident(
            incident_type=IncidentType.MISSING_PERSON,
            personnel_id=m.leader_id,
            mission_id=m.id,
            check_in_id=ci.id,
            last_location=ci.location or m.route or "",
            detail=f"missed check-in due {ci.due_at.isoformat()} on {m.id} — draft, needs human assessment",
            status=IncidentStatus.OPEN,
            sos_flag=False,
        )
    )
    db.add(AuditEvent(actor_id=None, action=AuditAction.CREATE, entity_type="Incident", entity_id=f"check-in {ci.id}", new_value="MISSING_PERSON draft (OPEN, not SOS)", source="SYNTHETIC_DEMO"))


def advance_checkins(db: Session, now: datetime | None = None) -> dict:
    """Background-worker step (APScheduler every minute; also POST /check-ins/advance).

    Advances every open check-in along DUE → GRACE → MISSED → LOCAL_ALERT →
    ESCALATION → EMERGENCY_ASSESSMENT based on elapsed grace windows.
    """
    now = now or _now()
    moved: list[dict] = []
    open_rows = db.query(FieldCheckIn).filter(FieldCheckIn.status != CheckInStatus.CHECKED_IN).all()
    missions = {m.id: m for m in db.query(FieldMission).filter(FieldMission.id.in_({c.mission_id for c in open_rows})).all()} if open_rows else {}
    for ci in open_rows:
        m = missions.get(ci.mission_id)
        grace = (m.grace_minutes or 15) if m else 15
        due = ci.due_at if ci.due_at.tzinfo else ci.due_at.replace(tzinfo=timezone.utc)
        elapsed_min = max(0.0, (now - due).total_seconds() / 60)
        target_idx = min(int(elapsed_min // max(grace, 1)), len(ESCALATION_LADDER) - 1)
        target = ESCALATION_LADDER[target_idx]
        old = ci.status if isinstance(ci.status, CheckInStatus) else CheckInStatus(_sval(ci.status))
        old_idx = ESCALATION_LADDER.index(old)
        if target_idx > old_idx:
            ci.status = target
            for i in range(old_idx + 1, target_idx + 1):
                if ESCALATION_LADDER[i] == CheckInStatus.MISSED and m is not None:
                    _ensure_draft_incident(db, ci, m)
                    from app.models.notification import NotificationType, Severity
                    from app.services.notification_service import notify_once

                    notify_once(
                        db, NotificationType.CHECK_IN_MISSED, Severity.WARNING, "FIELD_LEADER", "FieldCheckIn", ci.id,
                        f"Missed check-in on {m.id} (was due {ci.due_at.isoformat()}) — draft MISSING_PERSON incident raised",
                    )
                moved.append({"check_in": ci.id, "mission": ci.mission_id, "from": _sval(ESCALATION_LADDER[i - 1]), "to": _sval(ESCALATION_LADDER[i])})
            db.add(AuditEvent(actor_id=None, action=AuditAction.STATUS_TRANSITION, entity_type="FieldCheckIn", entity_id=ci.id, old_value=_sval(old), new_value=_sval(target), source="SYNTHETIC_DEMO"))
    db.commit()
    return {"advanced": moved}


def post_comms(db: Session, mid: str, author: str, message: str) -> MissionComms:
    _mission(db, mid)
    if not message.strip():
        raise HTTPException(status_code=400, detail="message required")
    row = MissionComms(mission_id=mid, author=author, message=message.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
