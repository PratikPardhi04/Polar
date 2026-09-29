import json
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditEvent
from app.models.cargo import Package, Shipment
from app.models.checkin import FieldCheckIn, MissionComms
from app.models.expedition import Expedition
from app.models.incident import Incident
from app.models.inventory import InventoryItem, InventoryTransaction
from app.models.mission import FieldMission
from app.models.personnel import Personnel, PersonnelReadinessEvent
from app.models.situation import ReportStatus, SituationReport


def _sval(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


def _on_day(col, day: date):
    return func.date(col) == day.isoformat()


def build_draft(db: Session, expedition_id: str, day: date, actor_id: str) -> SituationReport:
    exp = db.query(Expedition).filter(Expedition.id == expedition_id).first()
    if not exp:
        raise HTTPException(status_code=400, detail=f"unknown expedition {expedition_id}")

    people = db.query(Personnel).filter(Personnel.expedition_id == expedition_id).all()
    pids = [p.id for p in people]
    breakdown: dict[str, int] = {}
    for p in people:
        st = _sval(p.current_readiness)
        breakdown[st] = breakdown.get(st, 0) + 1
    changes = []
    if pids:
        for ev in db.query(PersonnelReadinessEvent).filter(PersonnelReadinessEvent.personnel_id.in_(pids), _on_day(PersonnelReadinessEvent.created_at, day)).all():
            who = next((p.full_name for p in people if p.id == ev.personnel_id), ev.personnel_id)
            changes.append({"name": who, "from": ev.from_state, "to": ev.to_state})

    ships = db.query(Shipment).filter(Shipment.expedition_id == expedition_id).all()
    ship_rows = [{"id": s.id, "status": _sval(s.status), "location": s.current_location} for s in ships]
    sids = [s.id for s in ships]
    pkg_transit = db.query(Package).filter(Package.shipment_id.in_(sids)).count() if sids else 0

    low = db.query(InventoryItem).filter(InventoryItem.status.in_(["CRITICAL", "WATCH"])).all()
    tx_today = db.query(InventoryTransaction).filter(_on_day(InventoryTransaction.created_at, day)).count()

    missions = db.query(FieldMission).filter(FieldMission.expedition_id == expedition_id).all()
    mids = [m.id for m in missions]
    mission_rows = [{"id": m.id, "objective": (m.objective or "")[:80], "status": _sval(m.status)} for m in missions]
    ci_today = db.query(FieldCheckIn).filter(FieldCheckIn.mission_id.in_(mids), _on_day(FieldCheckIn.created_at, day)).count() if mids else 0
    comms_today = db.query(MissionComms).filter(MissionComms.mission_id.in_(mids), _on_day(MissionComms.created_at, day)).count() if mids else 0

    open_inc = db.query(Incident).filter(Incident.mission_id.in_(mids)).filter(Incident.status.notin_(["RESOLVED", "CLOSED"])).all() if mids else []
    created_today = db.query(Incident).filter(Incident.mission_id.in_(mids), _on_day(Incident.created_at, day)).count() if mids else 0

    risks: list[str] = []
    for item in low:
        if _sval(item.status) == "CRITICAL":
            risks.append(f"CRITICAL stock: {item.name} ({item.quantity:g} {item.unit} @ {item.location})")
    for inc in open_inc:
        flag = "SOS — " if inc.sos_flag else ""
        risks.append(f"{flag}Open {_sval(inc.incident_type)} incident {inc.id} [{_sval(inc.status)}]")
    for s in ships:
        if _sval(s.status) == "DELAYED":
            risks.append(f"Shipment {s.id} DELAYED @ {s.current_location}")
    if not risks:
        risks.append("No critical risks flagged by rules this cycle.")

    sections = {
        "personnel": {"total": len(people), "breakdown": breakdown, "readiness_changes_today": changes},
        "cargo": {"shipments": ship_rows, "packages_in_transit": pkg_transit},
        "inventory": {"critical": [i.name for i in low if _sval(i.status) == "CRITICAL"], "watch": [i.name for i in low if _sval(i.status) == "WATCH"], "transactions_today": tx_today},
        "field_ops": {"missions": mission_rows, "check_ins_today": ci_today, "comms_today": comms_today},
        "incidents": {"open": [{"id": i.id, "type": _sval(i.incident_type), "status": _sval(i.status), "sos": bool(i.sos_flag)} for i in open_inc], "created_today": created_today},
        "risks_recommendations": risks,
    }
    draft = SituationReport(expedition_id=expedition_id, report_date=day, sections=json.dumps(sections), status=ReportStatus.DRAFT, created_by=actor_id)
    db.add(draft)
    db.flush()
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.CREATE, entity_type="SituationReport", entity_id=draft.id, new_value=f"DRAFT {expedition_id} {day.isoformat()}", source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(draft)
    return draft


def publish(db: Session, report_id: str, actor_id: str) -> SituationReport:
    rep = db.query(SituationReport).filter(SituationReport.id == report_id).first()
    if not rep:
        raise HTTPException(status_code=404, detail="report not found")
    current = _sval(rep.status)
    if current != "DRAFT":
        raise HTTPException(status_code=409, detail=f"only DRAFT reports can be published ({current})")
    rep.status = ReportStatus.PUBLISHED
    rep.published_by = actor_id
    rep.published_at = datetime.now()
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.PUBLISH, entity_type="SituationReport", entity_id=rep.id, new_value="PUBLISHED", source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(rep)
    return rep
