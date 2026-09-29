import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SyncedResult(str, enum.Enum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CONFLICT = "CONFLICT"
    ERROR = "ERROR"


class SyncedEvent(Base):
    """Server-side receipt log — re-uploaded event_ids are ACKed without re-applying."""

    __tablename__ = "synced_events"

    event_id = Column(String(128), primary_key=True)
    device_id = Column(String(128), nullable=False, default="")
    user_id = Column(String(128), nullable=False, default="")
    event_type = Column(String(64), nullable=False)
    entity_id = Column(String(256), nullable=False, default="")
    timestamp = Column(DateTime(timezone=True), nullable=True)
    payload = Column(Text, nullable=False, default="{}")
    result = Column(Enum(SyncedResult, name="synced_result", native_enum=False), nullable=False, default=SyncedResult.ACKNOWLEDGED)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConflictStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class SyncConflict(Base):
    """Offline inventory over-issue: conflicting events are NOT applied.

    Surfaced as ACTION REQUIRED until resolved via POST /sync/conflicts/{id}/resolve.
    """

    __tablename__ = "sync_conflicts"

    id = Column(String(36), primary_key=True, default=_uuid)
    entity_type = Column(String(64), nullable=False, default="InventoryItem")
    entity_id = Column(String(128), nullable=False, default="")
    event_ids = Column(Text, nullable=False, default="[]")  # JSON list
    reason = Column(Text, nullable=False, default="")
    status = Column(Enum(ConflictStatus, name="conflict_status", native_enum=False), nullable=False, default=ConflictStatus.OPEN)
    resolution = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
