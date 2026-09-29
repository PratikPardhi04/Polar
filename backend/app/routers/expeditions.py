from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.expedition import Expedition
from app.models.station import Station
from app.models.user import Role, User
from app.schemas.expedition import ExpeditionCreate, ExpeditionResponse, ExpeditionUpdate, StationResponse
from app.services.expedition_service import create_expedition, patch_expedition

router = APIRouter(prefix="/api/v1", tags=["expeditions"])

_write = require_role(Role.ADMIN, Role.EXPEDITION_LEADER)


@router.get("/stations", response_model=list[StationResponse])
def list_stations(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Station).order_by(Station.code).all()


@router.post("/expeditions", response_model=ExpeditionResponse, status_code=201)
def create(body: ExpeditionCreate, db: Session = Depends(get_db), user: User = Depends(_write)):
    return create_expedition(db, body, actor_id=user.id)


@router.get("/expeditions", response_model=list[ExpeditionResponse])
def list_all(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Expedition).order_by(Expedition.id).all()


@router.get("/expeditions/{exp_id}", response_model=ExpeditionResponse)
def get_one(exp_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    exp = db.query(Expedition).filter(Expedition.id == exp_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="expedition not found")
    return exp


@router.patch("/expeditions/{exp_id}", response_model=ExpeditionResponse)
def patch(exp_id: str, body: ExpeditionUpdate, db: Session = Depends(get_db), user: User = Depends(_write)):
    exp = db.query(Expedition).filter(Expedition.id == exp_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="expedition not found")
    return patch_expedition(db, exp, body, actor_id=user.id)
