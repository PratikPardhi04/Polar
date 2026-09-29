import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class IncidentType(str, enum.Enum):
    MEDICAL = "MEDICAL"
    MISSING_PERSON = "MISSING_PERSON"
    VEHICLE_BREAKDOWN = "VEHICLE_BREAKDOWN"
    FIRE = "FIRE"
    FUEL_SPILL = "FUEL_SPILL"
    COMMUNICATION_FAILURE = "COMMUNICATION_FAILURE"
    EXTREME_WEATHER = "EXTREME_WEATHER"
    EQUIPMENT_FAILURE = "EQUIPMENT_FAILURE"
    ENVIRONMENTAL_INCIDENT = "ENVIRONMENTAL_INCIDENT"


class IncidentStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSESSING = "ASSESSING"
    RESPONDING = "RESPONDING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Incident(Base):
    """Phase 4.3 creates the table + draft MISSING_PERSON rows from missed check-ins.
    Phase 5 builds the management panel, SOS wiring, and resource matching on top."""

    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=_uuid)
    incident_type = Column(Enum(IncidentType, name="incident_type", native_enum=False), nullable=False)
    personnel_id = Column(String(36), ForeignKey("personnel.id"), nullable=True)
    mission_id = Column(String(32), ForeignKey("field_missions.id"), nullable=True)
    check_in_id = Column(String(36), ForeignKey("field_check_ins.id"), nullable=True)
    last_location = Column(String(128), nullable=False, default="")
    detail = Column(Text, nullable=False, default="")
    status = Column(Enum(IncidentStatus, name="incident_status", native_enum=False), nullable=False, default=IncidentStatus.OPEN)
    sos_flag = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
