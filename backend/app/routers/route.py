from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.route_leg import RouteLeg
from app.models.user import User

router = APIRouter(prefix="/api/v1/route-legs", tags=["route"])


class LegResponse(BaseModel):
    id: str
    expedition_id: str | None
    seq: int
    origin: str
    destination: str
    mode: str
    capacity: str
    status: str
    delay_min: int

    model_config = {"from_attributes": False}


@router.get("", response_model=list[LegResponse])
def list_legs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(RouteLeg).order_by(RouteLeg.seq).all()
    return [LegResponse(id=r.id, expedition_id=r.expedition_id, seq=r.seq, origin=r.origin, destination=r.destination, mode=r.mode, capacity=r.capacity, status=r.status.value if hasattr(r.status, "value") else str(r.status), delay_min=r.delay_min or 0) for r in rows]
