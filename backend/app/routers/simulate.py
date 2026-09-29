from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import Role, User
from app.services import broadcaster, simulation_service

router = APIRouter(prefix="/api/v1/simulate", tags=["simulation (admin-only)"])

_admin = require_role(Role.ADMIN)


class RefBody(BaseModel):
    shipment_id: str | None = None
    mission_id: str | None = None
    personnel_id: str | None = None
    item_id: str | None = None
    station: str = "BHARATI"


class OutageBody(BaseModel):
    online: bool


@router.post("/cargo-delay")
def cargo_delay(body: RefBody, db: Session = Depends(get_db), user: User = Depends(_admin)):
    return simulation_service.simulate_cargo_delay(db, actor_id=user.id, shipment_id=body.shipment_id)


@router.post("/network-outage")
def network_outage(body: OutageBody, db: Session = Depends(get_db), user: User = Depends(_admin)):
    return simulation_service.simulate_network_outage(db, actor_id=user.id, online=body.online)


@router.post("/missed-check-in")
def missed_checkin(body: RefBody, db: Session = Depends(get_db), user: User = Depends(_admin)):
    return simulation_service.simulate_missed_checkin(db, actor_id=user.id, mission_id=body.mission_id)


@router.post("/sos")
async def sos(body: RefBody, db: Session = Depends(get_db), user: User = Depends(_admin)):
    out = simulation_service.trigger_sos(db, actor_id=user.id, mission_id=body.mission_id, personnel_id=body.personnel_id)
    for alert in out.get("sos_alerts", []):
        await broadcaster.broadcast("SOS", {"incident_id": alert.get("incident_id"), "mission_id": alert.get("mission_id"), "simulated": True})
    return out


@router.post("/inventory-shortage")
def inventory_shortage(body: RefBody, db: Session = Depends(get_db), user: User = Depends(_admin)):
    return simulation_service.simulate_inventory_shortage(db, actor_id=user.id, item_id=body.item_id)


@router.post("/weather-event")
def weather_event(body: RefBody, db: Session = Depends(get_db), user: User = Depends(_admin)):
    return simulation_service.simulate_weather_event(db, actor_id=user.id, station_ref=body.station)
