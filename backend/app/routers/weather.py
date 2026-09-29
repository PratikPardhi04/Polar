from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.station import Station
from app.models.user import User
from app.models.weather import WeatherSnapshot
from app.services.weather_service import fetch_live

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])


class WeatherResponse(BaseModel):
    station_code: str
    temp_c: float
    wind_kph: float
    visibility_m: float | None
    condition: str
    fetched_at: datetime | None
    source: str

    model_config = {"from_attributes": False}


def _station(db: Session, ref: str) -> Station:
    station = db.query(Station).filter((Station.id == ref) | (Station.code == ref.upper())).first()
    if not station:
        raise HTTPException(status_code=404, detail=f"unknown station {ref}")
    return station


def _out(station: Station, snap: WeatherSnapshot) -> WeatherResponse:
    return WeatherResponse(
        station_code=station.code,
        temp_c=snap.temp_c,
        wind_kph=snap.wind_kph,
        visibility_m=snap.visibility_m,
        condition=snap.condition,
        fetched_at=snap.fetched_at,
        source=snap.source,
    )


@router.get("/{station_ref}", response_model=WeatherResponse)
def current(station_ref: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Fetch live from Open-Meteo and cache as a WeatherSnapshot row.

    Falls back to the latest cached snapshot when the live API is unreachable.
    """
    station = _station(db, station_ref)
    try:
        live = fetch_live(station.latitude, station.longitude)
        snap = WeatherSnapshot(station_id=station.id, source="LIVE_API", **live)
        db.add(snap)
        db.commit()
        db.refresh(snap)
        return _out(station, snap)
    except Exception as exc:
        cached = db.query(WeatherSnapshot).filter(WeatherSnapshot.station_id == station.id).order_by(WeatherSnapshot.fetched_at.desc()).first()
        if cached:
            return _out(station, cached)
        raise HTTPException(status_code=503, detail=f"weather API unreachable and no cached snapshot: {exc}") from exc
