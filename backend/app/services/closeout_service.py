import html as htmlmod
import json
import os

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.asset import Asset, Vehicle
from app.models.audit import AuditAction, AuditEvent
from app.models.cargo import Shipment
from app.models.checkin import CheckInStatus, FieldCheckIn, MissionComms
from app.models.expedition import Expedition
from app.models.incident import Incident
from app.models.inventory import InventoryTransaction
from app.models.mission import FieldMission, FieldMissionMember, MissionStatus
from app.models.personnel import Personnel
from app.models.report import MissionOutcome, MissionReport, PhaseReport

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "generated_reports")

# check-ins at these stages mean the team is NOT accounted for
BLOCKING_CHECKIN_STATES = {"MISSED_CHECK_IN", "LOCAL_ALERT", "ESCALATION", "EMERGENCY_ASSESSMENT"}

RETURN_CONDITIONS = {"RETURNED", "LOST", "DAMAGED"}


def _sval(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


def _mission(db: Session, mid: str) -> FieldMission:
    m = db.query(FieldMission).filter(FieldMission.id == mid).first()
    if not m:
        raise HTTPException(status_code=404, detail="mission not found")
    return m


def _equipment_ids(m: FieldMission) -> list[str]:
    try:
        return json.loads(m.equipment_ids or "[]")
    except (ValueError, TypeError):
        return []


def _pdf(path: str, title: str, lines: list[tuple[str, str]], table: list[list[str]] | None = None):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    os.makedirs(os.path.dirname(path), exist_ok=True)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 6 * mm)]
    for key, val in lines:
        story += [Paragraph(f"<b>{htmlmod.escape(key)}</b>: {htmlmod.escape(val)}", styles["Normal"]), Spacer(1, 2 * mm)]
    if table:
        t = Table(table, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "grey"), ("BACKGROUND", (0, 0), (-1, 0), "lightgrey")]))
        story += [Spacer(1, 4 * mm), t]
    story += [Spacer(1, 6 * mm), Paragraph("Templated record (SYNTHETIC_DEMO where applicable) — not freeform LLM text.", styles["Italic"])]
    SimpleDocTemplate(path, pagesize=A4).build(story)


def close_mission(db: Session, mid: str, actor_id: str, closing_summary: str, outcome: MissionOutcome, vehicle_condition: str, equipment: dict[str, str]) -> MissionReport:
    m = _mission(db, mid)
    if _sval(m.status) != "RETURNED":
        raise HTTPException(status_code=409, detail=f"mission must be RETURNED before closeout (now {_sval(m.status)})")
    if not (closing_summary or "").strip():
        raise HTTPException(status_code=400, detail="closing_summary is required")
    if db.query(MissionReport).filter(MissionReport.mission_id == mid).first():
        raise HTTPException(status_code=409, detail="mission already closed with a report")

    # 1. team accounted for: no check-in stuck in escalation
    bad = db.query(FieldCheckIn).filter(FieldCheckIn.mission_id == mid, FieldCheckIn.status.in_(list(BLOCKING_CHECKIN_STATES))).all()
    if bad:
        raise HTTPException(status_code=409, detail=f"{len(bad)} check-in(s) unaccounted for ({_sval(bad[0].status)}); resolve escalation first")

    # 2. vehicle + equipment explicitly flagged
    if m.vehicle_id and vehicle_condition not in RETURN_CONDITIONS:
        raise HTTPException(status_code=400, detail="vehicle_condition must be one of RETURNED|LOST|DAMAGED")
    needed = set(_equipment_ids(m))
    if set(equipment or {}) != needed:
        raise HTTPException(status_code=400, detail=f"every equipment item must be flagged RETURNED|LOST|DAMAGED (expected {sorted(needed)})")
    for cond in (equipment or {}).values():
        if cond not in RETURN_CONDITIONS:
            raise HTTPException(status_code=400, detail=f"bad equipment condition {cond}")

    members = db.query(FieldMissionMember).filter(FieldMissionMember.mission_id == mid).all()
    team = []
    for mm in members:
        p = db.query(Personnel).filter(Personnel.id == mm.personnel_id).first()
        team.append({"name": p.full_name if p else mm.personnel_id, "readiness": _sval(p.current_readiness) if p else "?"})
    checkins = db.query(FieldCheckIn).filter(FieldCheckIn.mission_id == mid).order_by(FieldCheckIn.due_at).all()
    ci_rows = [{"due": str(c.due_at), "status": _sval(c.status), "note": c.note or ""} for c in checkins]
    incidents = db.query(Incident).filter(Incident.mission_id == mid).all()
    inc_rows = [{"id": i.id, "type": _sval(i.incident_type), "status": _sval(i.status)} for i in incidents]
    comms_n = db.query(MissionComms).filter(MissionComms.mission_id == mid).count()

    vehicle_desc, vehicle_name = "none assigned", ""
    if m.vehicle_id:
        v = db.query(Vehicle).filter(Vehicle.id == m.vehicle_id).first()
        if v:
            vehicle_name = v.registration_number or v.id
            vehicle_desc = f"{vehicle_name} [{vehicle_condition}]"
            if vehicle_condition == "DAMAGED":
                a = db.query(Asset).filter(Asset.id == v.asset_id).first()
                if a and _sval(a.status) == "IN_SERVICE":
                    a.status = "MAINTENANCE"
                    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.STATUS_TRANSITION, entity_type="Asset", entity_id=a.id, old_value="IN_SERVICE", new_value="MAINTENANCE", reason=f"returned DAMAGED from {mid}", source="SYNTHETIC_DEMO"))
    eq_rows = []
    for aid in _equipment_ids(m):
        cond = equipment[aid]
        a = db.query(Asset).filter(Asset.id == aid).first()
        eq_rows.append({"asset": a.name if a else aid, "condition": cond})
        if not a:
            continue
        if cond == "DAMAGED" and _sval(a.status) == "IN_SERVICE":
            a.status = "MAINTENANCE"
            db.add(AuditEvent(actor_id=actor_id, action=AuditAction.STATUS_TRANSITION, entity_type="Asset", entity_id=a.id, old_value="IN_SERVICE", new_value="MAINTENANCE", reason=f"returned DAMAGED from {mid}", source="SYNTHETIC_DEMO"))
        elif cond == "LOST":
            a.location = f"LOST — {mid}"
            db.add(AuditEvent(actor_id=actor_id, action=AuditAction.STATUS_TRANSITION, entity_type="Asset", entity_id=a.id, new_value=f"LOST — {mid}", source="SYNTHETIC_DEMO"))

    os.makedirs(REPORT_DIR, exist_ok=True)
    pdf_path = os.path.abspath(os.path.join(REPORT_DIR, f"{mid}_mission_report.pdf"))
    _pdf(
        pdf_path,
        f"POLARIS Mission Report — {mid} (SYNTHETIC_DEMO)",
        [("Objective", m.objective or ""), ("Outcome", _sval(outcome)), ("Summary", closing_summary), ("Vehicle", vehicle_desc), ("Check-ins", str(len(ci_rows))), ("Comms entries", str(comms_n)), ("Incidents", str(len(inc_rows)))],
        table=[["#", "Due", "Status", "Note"]] + [[str(i + 1), r["due"], r["status"], r["note"][:60]] for i, r in enumerate(ci_rows)] or [["—", "no check-ins", "—", "—"]],
    )
    rows_html = "".join(f"<tr><td>{htmlmod.escape(r['due'])}</td><td>{htmlmod.escape(r['status'])}</td><td>{htmlmod.escape(r['note'])}</td></tr>" for r in ci_rows)
    team_str = ", ".join(t["name"] for t in team) or "—"
    eq_str = ", ".join(f"{e['asset']} [{e['condition']}]" for e in eq_rows) or "—"
    inc_str = ", ".join(f"{i['id']} [{i['type']}/{i['status']}]" for i in inc_rows) or "none"
    page = (
        f"<h1>Mission Report — {htmlmod.escape(mid)}</h1>"
        f"<p><b>Objective:</b> {htmlmod.escape(m.objective or '')}</p>"
        f"<p><b>Outcome:</b> {htmlmod.escape(_sval(outcome))}</p>"
        f"<p><b>Team:</b> {htmlmod.escape(team_str)}</p>"
        f"<p><b>Vehicle:</b> {htmlmod.escape(vehicle_desc)}</p>"
        f"<p><b>Equipment:</b> {htmlmod.escape(eq_str)}</p>"
        f"<p><b>Summary:</b> {htmlmod.escape(closing_summary)}</p>"
        f"<h2>Check-in timeline ({len(ci_rows)})</h2><table><tr><th>Due</th><th>Status</th><th>Note</th></tr>{rows_html}</table>"
        f"<h2>Incidents ({len(inc_rows)})</h2><p>{htmlmod.escape(inc_str)}</p>"
    )
    rep = MissionReport(mission_id=mid, outcome=outcome, closing_summary=closing_summary, html=page, pdf_path=pdf_path)
    db.add(rep)
    db.flush()
    m.status = MissionStatus.CLOSED
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.CLOSE, entity_type="FieldMission", entity_id=mid, old_value="RETURNED", new_value="CLOSED", reason=closing_summary[:300], source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(rep)
    return rep


def close_expedition_phase(db: Session, expedition_id: str, actor_id: str, phase_name: str, summary: str) -> PhaseReport:
    exp = db.query(Expedition).filter(Expedition.id == expedition_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="expedition not found")
    if not (phase_name or "").strip():
        raise HTTPException(status_code=400, detail="phase_name is required")

    ships = db.query(Shipment).filter(Shipment.expedition_id == expedition_id).all()
    cargo_by_status: dict[str, int] = {}
    for s in ships:
        st = _sval(s.status)
        cargo_by_status[st] = cargo_by_status.get(st, 0) + 1
    delivered = sum(n for st, n in cargo_by_status.items() if st in ("RECEIVED_AT_STATION", "STORED"))

    people = db.query(Personnel).filter(Personnel.expedition_id == expedition_id).all()
    readiness: dict[str, int] = {}
    for p in people:
        st = _sval(p.current_readiness)
        readiness[st] = readiness.get(st, 0) + 1
    missions = db.query(FieldMission).filter(FieldMission.expedition_id == expedition_id).all()
    mids = [mm.id for mm in missions]
    incidents = db.query(Incident).filter(Incident.mission_id.in_(mids)).all() if mids else []
    consumed = sum(t.quantity or 0 for t in db.query(InventoryTransaction).filter(InventoryTransaction.txn_type.in_(["CONSUME", "ISSUE"])).all())

    rollup = {
        "cargo": {"shipments": len(ships), "by_status": cargo_by_status, "delivered": delivered},
        "personnel": {"total": len(people), "by_readiness": readiness},
        "missions": [{"id": mm.id, "status": _sval(mm.status)} for mm in missions],
        "incidents": {"total": len(incidents), "open": sum(1 for i in incidents if _sval(i.status) not in ("RESOLVED", "CLOSED"))},
        "inventory_consumed_total": consumed,
    }
    os.makedirs(REPORT_DIR, exist_ok=True)
    pdf_path = os.path.abspath(os.path.join(REPORT_DIR, f"{expedition_id}_{phase_name.replace(' ', '_')}_phase_report.pdf"))
    _pdf(
        pdf_path,
        f"POLARIS Expedition Phase Report — {expedition_id} / {phase_name}",
        [("Summary", summary or ""), ("Cargo delivered", f"{delivered}/{len(ships)} shipments"), ("Personnel", str(len(people))), ("Missions", str(len(missions))), ("Incidents", f"{rollup['incidents']['open']} open / {len(incidents)} total"), ("Inventory consumed", f"{consumed:g}")],
    )
    rep = PhaseReport(expedition_id=expedition_id, phase_name=phase_name, summary=summary or "", rollup=json.dumps(rollup), pdf_path=pdf_path)
    db.add(rep)
    db.flush()
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.CLOSE, entity_type="Expedition", entity_id=expedition_id, old_value=None, new_value=f"phase closed: {phase_name}", reason=(summary or "")[:300], source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(rep)
    return rep
