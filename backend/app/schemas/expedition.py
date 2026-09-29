from datetime import date

from pydantic import BaseModel, Field

from app.models.expedition import DataSource, ExpeditionStatus


class StationResponse(BaseModel):
    id: str
    code: str
    name: str
    latitude: float
    longitude: float
    description: str = ""

    model_config = {"from_attributes": True}


class ExpeditionCreate(BaseModel):
    id: str = Field(pattern=r"^EXP-[A-Z0-9\-]+$", examples=["EXP-46ISEA-2026"])
    name: str
    start_date: date | None = None
    end_date: date | None = None
    primary_station_id: str = Field(description="Station.id or Station.code (e.g. BHARATI)")
    mission_type: str = "Polar Environmental Monitoring"
    description: str = ""
    source: DataSource = DataSource.SYNTHETIC_DEMO


class ExpeditionUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    primary_station_id: str | None = None
    mission_type: str | None = None
    status: ExpeditionStatus | None = None
    description: str | None = None


class ExpeditionResponse(BaseModel):
    id: str
    name: str
    start_date: date | None
    end_date: date | None
    primary_station_id: str
    mission_type: str
    status: ExpeditionStatus
    description: str
    source: DataSource
    primary_station: StationResponse | None = None

    model_config = {"from_attributes": True}
