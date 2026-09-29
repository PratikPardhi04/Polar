from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.notification import Notification, NotificationStatus, NotificationType, Severity, SimulatedAlert


def _sval(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


def notify_once(
    db: Session,
    ntype: NotificationType,
    severity: Severity,
    target_role: str,
    entity_type: str,
    entity_id: str,
    message: str,
) -> Notification | None:
    """Create unless an UNREAD notification for the same (type, entity) already exists."""
    existing = (
        db.query(Notification)
        .filter(Notification.notif_type == ntype, Notification.entity_type == entity_type, Notification.entity_id == entity_id, Notification.status == NotificationStatus.UNREAD)
        .first()
    )
    if existing:
        return None
    n = Notification(notif_type=ntype, severity=severity, target_role=target_role, entity_type=entity_type, entity_id=entity_id, message=message)
    db.add(n)
    db.flush()
    return n


def log_simulated_alert(db: Session, channel: str, recipient: str, subject: str, body: str, entity_type: str = "", entity_id: str = "") -> SimulatedAlert:
    row = SimulatedAlert(channel=channel, recipient=recipient, subject=subject, body=body, entity_type=entity_type, entity_id=entity_id, label="SIMULATED")
    db.add(row)
    db.flush()
    return row


def notify_sos(db: Session, incident_id: str, detail: str):
    notify_once(db, NotificationType.SOS, Severity.CRITICAL, "EMERGENCY_COORDINATOR", "Incident", incident_id, f"SOS received: {detail}")
    for channel, recipient in (("SMS", "on-call EMERGENCY_COORDINATOR"), ("EMAIL", "command-centre@bharati.in")):
        log_simulated_alert(db, channel, recipient, f"[SIMULATED] SOS {incident_id}", f"Would send {channel} to {recipient}: SOS incident {incident_id}. {detail}", "Incident", incident_id)


def notify_medical(db: Session, incident_id: str, detail: str):
    for channel, recipient in (("SMS", "on-call MEDICAL_OFFICER"), ("EMAIL", "medical@bharati.in")):
        log_simulated_alert(db, channel, recipient, f"[SIMULATED] MEDICAL {incident_id}", f"Would send {channel} to {recipient}: medical incident {incident_id}. {detail}", "Incident", incident_id)


def sweep_maintenance_due(db: Session, within_days: int = 7) -> int:
    """Lazy rule: assets with next_maintenance due soon get one UNREAD notice each."""
    now = datetime.now(timezone.utc).date()
    horizon = now + timedelta(days=within_days)
    made = 0
    for asset in db.query(Asset).filter(Asset.next_maintenance.isnot(None)).all():
        if _sval(asset.status) == "RETIRED" or not asset.next_maintenance or asset.next_maintenance > horizon:
            continue
        overdue = asset.next_maintenance < now
        if notify_once(
            db,
            NotificationType.MAINTENANCE_DUE,
            Severity.WARNING,
            "ENGINEER",
            "Asset",
            asset.id,
            f"{asset.name} ({asset.serial_number}) maintenance {'OVERDUE since' if overdue else 'due'} {asset.next_maintenance.isoformat()}",
        ):
            made += 1
    if made:
        db.commit()
    return made
