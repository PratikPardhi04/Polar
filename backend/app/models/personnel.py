import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ReadinessState(str, enum.Enum):
    NOMINATED = "NOMINATED"
    DOCUMENTS_PENDING = "DOCUMENTS_PENDING"
    MEDICAL_SCHEDULED = "MEDICAL_SCHEDULED"
    MEDICAL_CLEARED = "MEDICAL_CLEARED"
    TRAINING_COMPLETED = "TRAINING_COMPLETED"
    MISSION_READY = "MISSION_READY"
    INDUCTED = "INDUCTED"
    AT_STATION = "AT_STATION"
    FIELD_DEPLOYED = "FIELD_DEPLOYED"
    DE_INDUCTION_SCHEDULED = "DE_INDUCTION_SCHEDULED"
    RETURNED = "RETURNED"
    CLOSED_OUT = "CLOSED_OUT"


# Strict linear chain — no skipped states, no going back.
READINESS_ORDER = [s.value for s in ReadinessState]
ALLOWED_TRANSITIONS: dict[str, set[str]] = {READINESS_ORDER[i]: {READINESS_ORDER[i + 1]} for i in range(len(READINESS_ORDER) - 1)}
ALLOWED_TRANSITIONS[READINESS_ORDER[-1]] = set()


class Personnel(Base):
    __tablename__ = "personnel"

    id = Column(String(36), primary_key=True, default=_uuid)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(64), nullable=True, default="")
    role = Column(String(64), nullable=False, default="SCIENTIST")
    expedition_id = Column(String(64), ForeignKey("expeditions.id"), nullable=True)
    current_readiness = Column(Enum(ReadinessState, name="readiness_state", native_enum=False), nullable=False, default=ReadinessState.NOMINATED)
    emergency_contact = Column(String(255), nullable=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PersonnelReadinessEvent(Base):
    """Movement/history trail: every readiness transition appends one row."""

    __tablename__ = "personnel_readiness_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    personnel_id = Column(String(36), ForeignKey("personnel.id"), nullable=False, index=True)
    from_state = Column(String(32), nullable=True)
    to_state = Column(String(32), nullable=False)
    actor_id = Column(String(36), nullable=True)
    reason = Column(Text, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
