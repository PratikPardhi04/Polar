import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AuditAction:
    CREATE = "CREATE"
    STATUS_TRANSITION = "STATUS_TRANSITION"
    APPROVE = "APPROVE"
    OVERRIDE = "OVERRIDE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    PUBLISH = "PUBLISH"
    CLOSE = "CLOSE"


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(32), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(128), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    source = Column(String(32), nullable=False, default="SYNTHETIC_DEMO")
