import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class NotificationType(str, enum.Enum):
    STOCK_CRITICAL = "STOCK_CRITICAL"
    CHECK_IN_MISSED = "CHECK_IN_MISSED"
    SOS = "SOS"
    CARGO_DELAYED = "CARGO_DELAYED"
    MAINTENANCE_DUE = "MAINTENANCE_DUE"
    WEATHER_ALERT = "WEATHER_ALERT"
    AI_ADVISORY = "AI_ADVISORY"  # the only type creatable via POST /notifications (AI drafts for human ack)


class Severity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class NotificationStatus(str, enum.Enum):
    UNREAD = "UNREAD"
    READ = "READ"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=_uuid)
    notif_type = Column(Enum(NotificationType, name="notification_type", native_enum=False), nullable=False)
    severity = Column(Enum(Severity, name="severity", native_enum=False), nullable=False, default=Severity.WARNING)
    target_role = Column(String(32), nullable=False, default="")
    entity_type = Column(String(64), nullable=False, default="")
    entity_id = Column(String(128), nullable=False, default="")
    message = Column(Text, nullable=False, default="")
    status = Column(Enum(NotificationStatus, name="notification_status", native_enum=False), nullable=False, default=NotificationStatus.UNREAD)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SimulatedAlert(Base):
    """Log of an SMS/email that WOULD have been sent. No real provider —
    every row is explicitly labeled SIMULATED."""

    __tablename__ = "simulated_alerts"

    id = Column(String(36), primary_key=True, default=_uuid)
    channel = Column(String(16), nullable=False)  # SMS | EMAIL
    recipient = Column(String(255), nullable=False, default="")
    subject = Column(String(255), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    entity_type = Column(String(64), nullable=False, default="")
    entity_id = Column(String(128), nullable=False, default="")
    label = Column(String(32), nullable=False, default="SIMULATED")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
