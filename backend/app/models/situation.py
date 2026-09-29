import enum
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ReportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class SituationReport(Base):
    """Daily Situation Report. Drafts are NEVER official until a human
    (Station/Expedition Leader) publishes — no auto-publish path exists."""

    __tablename__ = "situation_reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    expedition_id = Column(String(64), ForeignKey("expeditions.id"), nullable=False, index=True)
    report_date = Column(Date, nullable=False, index=True)
    sections = Column(Text, nullable=False, default="{}")  # JSON: personnel/cargo/inventory/field_ops/incidents/risks
    status = Column(Enum(ReportStatus, name="report_status", native_enum=False), nullable=False, default=ReportStatus.DRAFT)
    created_by = Column(String(36), nullable=True)
    published_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
