import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class PlanKind(str, enum.Enum):
    LOGISTICS = "LOGISTICS"
    INVENTORY = "INVENTORY"
    EMERGENCY = "EMERGENCY"
    GENERAL = "GENERAL"


class PlanStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PlanDraft(Base):
    """AI-proposed action awaiting human approval. Nothing executes on create —
    APPROVE/REJECT is a separate, audited human step (Ground Rule 6)."""

    __tablename__ = "plan_drafts"

    id = Column(String(36), primary_key=True, default=_uuid)
    title = Column(String(255), nullable=False)
    kind = Column(Enum(PlanKind, name="plan_kind", native_enum=False), nullable=False, default=PlanKind.GENERAL)
    body = Column(Text, nullable=False, default="{}")  # JSON
    status = Column(Enum(PlanStatus, name="plan_status", native_enum=False), nullable=False, default=PlanStatus.DRAFT)
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
