import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditEvent
from app.models.cargo import Package
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.inventory import InventoryItem, available_stock, validate_issue
from app.models.mission import FieldMission
from app.models.personnel import Personnel
from app.models.sync import ConflictStatus, SyncedEvent, SyncedResult, SyncConflict
from app.schemas.sync import ConflictResponse, SosAlert, SyncBatchRequest, SyncBatchResponse, SyncError
from app.services.inventory_service import apply_transaction

SOS_ESCALATION = {"OPEN": "ASSESSING", "ASSESSING": "RESPONDING"}


def _parse_ts(raw: str):
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None
    except Exception:
        return None


def _conflict_out(c: SyncConflict) -> ConflictResponse:
    return ConflictResponse(
        id=c.id,
        entity_type=c.entity_type,
        entity_id=c.entity_id,
        event_ids=json.loads(c.event_ids or "[]"),
        reason=c.reason or "",
        status=c.status.value if hasattr(c.status, "value") else str(c.status),
    )


def _resolve_item(db: Session, ref: str, payload: dict) -> InventoryItem | None:
    ref = (ref or payload.get("item") or payload.get("item_id") or "").strip()
    if not ref:
        return None
    item = db.query(InventoryItem).filter(InventoryItem.id == ref).first()
    if item:
        return item
    return db.query(InventoryItem).filter(func.lower(InventoryItem.name) == ref.lower()).first()


def _store(db: Session, ev, result: SyncedResult):
    db.add(
        SyncedEvent(
            event_id=ev.event_id,
            device_id=ev.device_id,
            user_id=ev.user_id,
            event_type=ev.event_type,
            entity_id=ev.entity_id,
            timestamp=_parse_ts(ev.timestamp),
            payload=json.dumps(ev.payload or {}),
            result=result,
        )
    )


def _handle_sos(db: Session, ev, actor_id: str) -> SosAlert:
    """Offline emergency packet → auto-create (or escalate) an OPEN SOS incident.

    Never dispatches rescue on its own — the incident waits for human response
    (Phase 5.3 notifications + 6.x AI recommendation both keep a human gate).
    """
    p = ev.payload or {}
    raw_type = str(p.get("incident_type", "MISSING_PERSON")).upper()
    try:
        itype = IncidentType(raw_type)
    except ValueError:
        itype = IncidentType.MISSING_PERSON
    personnel_id = p.get("personnel_id") or None
    mission_id = p.get("mission_id") or None
    if personnel_id and not db.query(Personnel).filter(Personnel.id == personnel_id).first():
        raise HTTPException(status_code=400, detail=f"unknown personnel_id {personnel_id}")
    if mission_id and not db.query(FieldMission).filter(FieldMission.id == mission_id).first():
        raise HTTPException(status_code=400, detail=f"unknown mission_id {mission_id}")

    candidates = db.query(Incident).filter(Incident.sos_flag.is_(True), Incident.status.in_(["OPEN", "ASSESSING"])).all()
    existing = next((c for c in candidates if c.mission_id == mission_id and c.personnel_id == personnel_id), None)
    if existing is None:
        inc = Incident(
            incident_type=itype,
            personnel_id=personnel_id,
            mission_id=mission_id,
            last_location=str(p.get("location", "")),
            detail=f"SOS from {ev.device_id}: {p.get('note', '')} "
            f"(battery {p.get('battery_pct', '?')}%, comm {p.get('comm_status', '?')}, team {p.get('team', '?')}, ETA return {p.get('expected_return', '?')})",
            status=IncidentStatus.OPEN,
            sos_flag=True,
        )
        db.add(inc)
        db.flush()
        db.add(AuditEvent(actor_id=actor_id, action=AuditAction.CREATE, entity_type="Incident", entity_id=inc.id, new_value=f"{itype.value} SOS OPEN", source="SYNTHETIC_DEMO"))
        from app.services.notification_service import notify_sos

        notify_sos(db, inc.id, f"{itype.value} from {ev.device_id} @ {p.get('location', '?')}")
        _store(db, ev, SyncedResult.ACKNOWLEDGED)
        return SosAlert(incident_id=inc.id, mission_id=mission_id, personnel_id=personnel_id, escalated=False)

    old = existing.status.value if hasattr(existing.status, "value") else str(existing.status)
    nxt = SOS_ESCALATION.get(old)
    if nxt:
        existing.status = IncidentStatus(nxt)
        db.add(AuditEvent(actor_id=actor_id, action=AuditAction.STATUS_TRANSITION, entity_type="Incident", entity_id=existing.id, old_value=old, new_value=nxt, reason=f"repeat SOS {ev.event_id}", source="SYNTHETIC_DEMO"))
    _store(db, ev, SyncedResult.ACKNOWLEDGED)
    return SosAlert(incident_id=existing.id, mission_id=mission_id, personnel_id=personnel_id, escalated=nxt is not None)


def process_batch(db: Session, batch: SyncBatchRequest, actor_id: str) -> SyncBatchResponse:
    events = sorted(batch.events, key=lambda e: e.timestamp or "")
    acked: list[str] = []
    conflicts: list[ConflictResponse] = []
    errors: list[SyncError] = []

    # idempotency first: already-seen ids ACK without re-applying
    fresh = []
    for ev in events:
        if db.query(SyncedEvent).filter(SyncedEvent.event_id == ev.event_id).first():
            acked.append(ev.event_id)
        else:
            fresh.append(ev)

    # group offline INVENTORY_ISSUE events per item; combined total vs server stock
    issues: dict[str, list] = {}
    issue_item: dict[str, InventoryItem] = {}
    for ev in fresh:
        if ev.event_type == "INVENTORY_ISSUE":
            qty = ev.payload.get("quantity", 0) if isinstance(ev.payload, dict) else 0
            try:
                qty = float(qty)
            except (TypeError, ValueError):
                _store(db, ev, SyncedResult.ERROR)
                errors.append(SyncError(event_id=ev.event_id, detail="quantity must be numeric"))
                continue
            item = _resolve_item(db, ev.entity_id, ev.payload or {})
            if not item:
                _store(db, ev, SyncedResult.ERROR)
                errors.append(SyncError(event_id=ev.event_id, detail=f"unknown inventory item '{ev.entity_id}'"))
                continue
            issues.setdefault(item.id, []).append((ev, qty))
            issue_item[item.id] = item

    conflicted_ids: set[str] = set()
    for item_id, pairs in issues.items():
        item = issue_item[item_id]
        total = sum(q for _, q in pairs)
        ok, why = validate_issue(item.quantity or 0.0, item.reserved_quantity or 0.0, total)
        if not ok:
            ids = [ev.event_id for ev, _ in pairs]
            conflicted_ids.update(ids)
            c = SyncConflict(
                entity_type="InventoryItem",
                entity_id=item.id,
                event_ids=json.dumps(ids),
                reason=f"offline issues total {total} vs available {available_stock(item.quantity or 0.0, item.reserved_quantity or 0.0)} "
                f"(on hand {item.quantity}, reserved {item.reserved_quantity}): {why}",
            )
            db.add(c)
            db.flush()
            for ev, _ in pairs:
                _store(db, ev, SyncedResult.CONFLICT)
            db.add(AuditEvent(actor_id=actor_id, action=AuditAction.CREATE, entity_type="SyncConflict", entity_id=c.id, new_value=f"{len(ids)} events on {item.name}", source="SYNTHETIC_DEMO"))
            db.flush()
            conflicts.append(_conflict_out(c))

    # apply everything else in timestamp order
    errored_ids = {er.event_id for er in errors}
    sos_alerts: list[SosAlert] = []
    for ev in fresh:
        if ev.event_id in conflicted_ids or ev.event_id in errored_ids:
            continue
        try:
            if ev.event_type == "SOS":
                sos_alerts.append(_handle_sos(db, ev, actor_id))
                acked.append(ev.event_id)
            elif ev.event_type == "INVENTORY_ISSUE":
                item = _resolve_item(db, ev.entity_id, ev.payload or {})
                qty = float(ev.payload.get("quantity", 0))
                apply_transaction(db, item.id, "ISSUE", qty, actor_id=actor_id, note=f"offline sync {ev.event_id} from {ev.device_id}")
                _store(db, ev, SyncedResult.ACKNOWLEDGED)
                acked.append(ev.event_id)
            elif ev.event_type == "CARGO_SCANNED":
                pid = (ev.payload or {}).get("package_id") or ev.entity_id
                pkg = db.query(Package).filter(Package.id == pid).first()
                if not pkg:
                    _store(db, ev, SyncedResult.ERROR)
                    errors.append(SyncError(event_id=ev.event_id, detail=f"package {pid} not found"))
                    continue
                loc = (ev.payload or {}).get("location")
                if loc:
                    pkg.location = loc
                to_status = (ev.payload or {}).get("to_status")
                if to_status:
                    from app.services.cargo_service import transition_package

                    transition_package(db, pkg, to_status, actor_id=actor_id, reason=f"offline scan {ev.event_id}", location=loc)
                else:
                    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.STATUS_TRANSITION, entity_type="Package", entity_id=pkg.id, old_value=None, new_value=f"scan @ {pkg.location}", source="SYNTHETIC_DEMO"))
                _store(db, ev, SyncedResult.ACKNOWLEDGED)
                acked.append(ev.event_id)
            else:
                # FIELD_CHECK_IN / READINESS_NOTE / future types: receipted now, processed by Phase 4+ pipelines
                db.add(AuditEvent(actor_id=actor_id, action=AuditAction.CREATE, entity_type="SyncedEvent", entity_id=ev.event_id, new_value=ev.event_type, source="SYNTHETIC_DEMO"))
                _store(db, ev, SyncedResult.ACKNOWLEDGED)
                acked.append(ev.event_id)
        except HTTPException as exc:
            _store(db, ev, SyncedResult.ERROR)
            errors.append(SyncError(event_id=ev.event_id, detail=exc.detail))
        except Exception as exc:
            _store(db, ev, SyncedResult.ERROR)
            errors.append(SyncError(event_id=ev.event_id, detail=str(exc)[:300]))

    db.commit()
    # refresh conflict responses with ids assigned at flush
    return SyncBatchResponse(acknowledged=acked, conflicts=conflicts, errors=errors, sos_alerts=sos_alerts)


def resolve_conflict(db: Session, conflict_id: str, resolution: str, actor_id: str, note: str = "") -> ConflictResponse:
    c = db.query(SyncConflict).filter(SyncConflict.id == conflict_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="conflict not found")
    if (c.status.value if hasattr(c.status, "value") else str(c.status)) != "OPEN":
        raise HTTPException(status_code=409, detail="conflict already resolved")
    if resolution == "APPLY_ANYWAY":
        ids: list[str] = json.loads(c.event_ids or "[]")
        for eid in ids:
            row = db.query(SyncedEvent).filter(SyncedEvent.event_id == eid).first()
            if not row:
                continue
            payload = json.loads(row.payload or "{}")
            qty = float(payload.get("quantity", 0))
            apply_transaction(db, c.entity_id, "ISSUE", qty, actor_id=actor_id, note=f"conflict {c.id} APPLY_ANYWAY: {note}")
            row.result = SyncedResult.ACKNOWLEDGED
    c.status = ConflictStatus.RESOLVED
    c.resolution = resolution
    db.add(AuditEvent(actor_id=actor_id, action=AuditAction.APPROVE, entity_type="SyncConflict", entity_id=c.id, new_value=resolution, reason=note, source="SYNTHETIC_DEMO"))
    db.commit()
    db.refresh(c)
    return _conflict_out(c)
