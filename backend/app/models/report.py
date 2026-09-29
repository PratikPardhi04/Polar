import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class MissionOutcome(str, enum.Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    ABORTED = "ABORTED"


class MissionReport(Base):
    __tablename__ = "mission_reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    mission_id = Column(String(32), ForeignKey("field_missions.id"), nullable=False, unique=True, index=True)
    outcome = Column(Enum(MissionOutcome, name="mission_outcome", native_enum=False), nullable=False)
    closing_summary = Column(Text, nullable=False, default="")
    html = Column(Text, nullable=False, default="")
    pdf_path = Column(String(512), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PhaseReport(Base):
    __tablename__ = "phase_reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    expedition_id = Column(String(64), ForeignKey("expeditions.id"), nullable=False, index=True)
    phase_name = Column(String(128), nullable=False)
    summary = Column(Text, nullable=False, default="")
    rollup = Column(Text, nullable=False, default="{}")  # JSON
    pdf_path = Column(String(512), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
