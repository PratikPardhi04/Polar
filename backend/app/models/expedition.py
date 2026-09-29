import enum
from datetime import date

from sqlalchemy import Column, Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ExpeditionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PLANNED", "CANCELLED"},
    "PLANNED": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"ON_HOLD", "COMPLETED"},
    "ON_HOLD": {"ACTIVE", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


class DataSource(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    SYNTHETIC_DEMO = "SYNTHETIC_DEMO"
    LIVE_API = "LIVE_API"


class Expedition(Base):
    __tablename__ = "expeditions"

    id = Column(String(64), primary_key=True)  # e.g. EXP-46ISEA-2026
    name = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    primary_station_id = Column(String(36), ForeignKey("stations.id"), nullable=False)
    mission_type = Column(String(128), nullable=False, default="Polar Environmental Monitoring")
    status = Column(Enum(ExpeditionStatus, name="expedition_status", native_enum=False), nullable=False, default=ExpeditionStatus.DRAFT)
    description = Column(Text, nullable=True, default="")
    source = Column(Enum(DataSource, name="data_source", native_enum=False), nullable=False, default=DataSource.SYNTHETIC_DEMO)

    primary_station = relationship("Station", lazy="joined")


def check_transition(old: str, new: str) -> bool:
    return new in ALLOWED_TRANSITIONS.get(old, set())
