import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class CheckInStatus(str, enum.Enum):
    DUE = "CHECK_IN_DUE"
    GRACE = "GRACE_PERIOD"
    MISSED = "MISSED_CHECK_IN"
    LOCAL_ALERT = "LOCAL_ALERT"
    ESCALATION = "ESCALATION"
    EMERGENCY_ASSESSMENT = "EMERGENCY_ASSESSMENT"
    CHECKED_IN = "CHECKED_IN"  # terminal success


# escalation ladder driven by elapsed grace windows since due_at
ESCALATION_LADDER = [
    CheckInStatus.DUE,
    CheckInStatus.GRACE,
    CheckInStatus.MISSED,
    CheckInStatus.LOCAL_ALERT,
    CheckInStatus.ESCALATION,
    CheckInStatus.EMERGENCY_ASSESSMENT,
]


class FieldCheckIn(Base):
    __tablename__ = "field_check_ins"

    id = Column(String(36), primary_key=True, default=_uuid)
    mission_id = Column(String(32), ForeignKey("field_missions.id"), nullable=False, index=True)
    due_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(CheckInStatus, name="checkin_status", native_enum=False), nullable=False, default=CheckInStatus.DUE)
    checked_in_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, nullable=True, default="")
    location = Column(String(128), nullable=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MissionComms(Base):
    """Simulated radio/comms log — free-text trail, separate from formal check-ins."""

    __tablename__ = "mission_comms"

    id = Column(String(36), primary_key=True, default=_uuid)
    mission_id = Column(String(32), ForeignKey("field_missions.id"), nullable=False, index=True)
    author = Column(String(255), nullable=False, default="")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
