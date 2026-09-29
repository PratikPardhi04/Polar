import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class LegStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    DELAYED = "DELAYED"


class RouteLeg(Base):
    """Goa → Mumbai → Cape Town → Antarctica → Bharati logistics graph."""

    __tablename__ = "route_legs"

    id = Column(String(36), primary_key=True, default=_uuid)
    expedition_id = Column(String(64), ForeignKey("expeditions.id"), nullable=True, index=True)
    seq = Column(Integer, nullable=False, default=0)
    origin = Column(String(128), nullable=False)
    destination = Column(String(128), nullable=False)
    mode = Column(String(64), nullable=False, default="SHIP")
    departure = Column(DateTime(timezone=True), nullable=True)
    eta = Column(DateTime(timezone=True), nullable=True)
    capacity = Column(String(64), nullable=False, default="")
    status = Column(Enum(LegStatus, name="leg_status", native_enum=False), nullable=False, default=LegStatus.SCHEDULED)
    delay_min = Column(Integer, nullable=False, default=0)
