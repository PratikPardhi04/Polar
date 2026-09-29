import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class MissionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    APPROVED = "APPROVED"
    DEPLOYED = "DEPLOYED"
    ACTIVE = "ACTIVE"
    ABORTED = "ABORTED"
    RETURNED = "RETURNED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


ALLOWED_MISSION_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PLANNED", "CANCELLED"},
    "PLANNED": {"APPROVED", "CANCELLED"},
    "APPROVED": {"DEPLOYED", "CANCELLED"},
    "DEPLOYED": {"ACTIVE", "ABORTED"},
    "ACTIVE": {"RETURNED", "ABORTED"},
    "ABORTED": {"RETURNED"},
    "RETURNED": {"CLOSED"},
    "CLOSED": set(),
    "CANCELLED": set(),
}

# personnel readiness states that count as "ready" for field deployment
READY_STATES = {"MISSION_READY", "INDUCTED", "AT_STATION", "FIELD_DEPLOYED"}


class FieldMission(Base):
    __tablename__ = "field_missions"

    id = Column(String(32), primary_key=True)  # FM-001 style
    expedition_id = Column(String(64), ForeignKey("expeditions.id"), nullable=False, index=True)
    objective = Column(Text, nullable=False, default="")
    leader_id = Column(String(36), ForeignKey("personnel.id"), nullable=True)
    vehicle_id = Column(String(36), ForeignKey("vehicles.id"), nullable=True)
    equipment_ids = Column(Text, nullable=False, default="[]")  # JSON list of asset ids
    start = Column(DateTime(timezone=True), nullable=True)
    expected_return = Column(DateTime(timezone=True), nullable=True)
    route = Column(Text, nullable=False, default="")
    check_in_interval_minutes = Column(Integer, nullable=False, default=60)
    grace_minutes = Column(Integer, nullable=False, default=15)
    emergency_kit = Column(Boolean, nullable=False, default=False)
    emergency_plan = Column(Text, nullable=False, default="")
    status = Column(Enum(MissionStatus, name="mission_status", native_enum=False), nullable=False, default=MissionStatus.DRAFT)


class FieldMissionMember(Base):
    __tablename__ = "field_mission_members"

    id = Column(String(36), primary_key=True, default=_uuid)
    mission_id = Column(String(32), ForeignKey("field_missions.id"), nullable=False, index=True)
    personnel_id = Column(String(36), ForeignKey("personnel.id"), nullable=False, index=True)
    role = Column(String(64), nullable=False, default="MEMBER")
