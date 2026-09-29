from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.forecast_service import forecast_all

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/inventory-forecast")
def inventory_forecast(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    window_days: int = Query(default=30, ge=1, le=365),
    lead_time_days: int = Query(default=14, ge=0, le=365),
    safety_days: int = Query(default=7, ge=0, le=365),
    method: str = Query(default="sma", pattern="^(sma|ewma)$"),
    only_at_risk: bool = Query(default=False),
):
    return forecast_all(db, window_days, lead_time_days, safety_days, method, only_at_risk)
