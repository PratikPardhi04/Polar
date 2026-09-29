import uuid

from sqlalchemy import Column, Float, String, Text

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Station(Base):
    __tablename__ = "stations"

    id = Column(String(36), primary_key=True, default=_uuid)
    code = Column(String(32), unique=True, nullable=False, index=True)  # BHARATI|MAITRI|HIMADRI
    name = Column(String(128), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    description = Column(Text, nullable=True, default="")


STATION_SEED = [
    {"code": "BHARATI", "name": "Bharati Station", "latitude": -69.4090, "longitude": 76.1866, "description": "Indian Antarctic station, Larsemann Hills — demo focus EXP-46ISEA-2026"},
    {"code": "MAITRI", "name": "Maitri Station", "latitude": -70.7650, "longitude": 11.7270, "description": "Indian Antarctic station, Schirmacher Oasis"},
    {"code": "HIMADRI", "name": "Himadri Station", "latitude": 78.9220, "longitude": 11.8500, "description": "Indian Arctic station, Svalbard"},
]
