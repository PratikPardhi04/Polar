import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class WeatherSnapshot(Base):
    """Cached Open-Meteo observation per station. Appended on every fetch;
    consumers read the latest row per station_id."""

    __tablename__ = "weather_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    station_id = Column(String(36), ForeignKey("stations.id"), nullable=False, index=True)
    temp_c = Column(Float, nullable=False)
    wind_kph = Column(Float, nullable=False)
    visibility_m = Column(Float, nullable=True)
    condition = Column(String(32), nullable=False, default="UNKNOWN")
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source = Column(String(32), nullable=False, default="LIVE_API")
