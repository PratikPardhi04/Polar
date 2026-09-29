from datetime import datetime

from pydantic import BaseModel

from app.models.incident import IncidentStatus, IncidentType


class IncidentCreate(BaseModel):
    incident_type: IncidentType
    personnel_id: str | None = None
    mission_id: str | None = None
    last_location: str = ""
    detail: str = ""


class IncidentUpdate(BaseModel):
    last_location: str | None = None
    detail: str | None = None
    personnel_id: str | None = None
    mission_id: str | None = None


class IncidentStatusUpdate(BaseModel):
    to_status: IncidentStatus
    reason: str = ""


class IncidentResponse(BaseModel):
    id: str
    incident_type: IncidentType
    personnel_id: str | None
    mission_id: str | None
    last_location: str
    detail: str
    status: IncidentStatus
    sos_flag: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PersonBrief(BaseModel):
    id: str
    full_name: str
    readiness: str


class MissionBrief(BaseModel):
    id: str
    objective: str
    status: str


class VehicleBrief(BaseModel):
    id: str
    registration_number: str
    asset_status: str


class IncidentDetail(BaseModel):
    incident: IncidentResponse
    person: PersonBrief | None = None
    mission: MissionBrief | None = None
    team: list[PersonBrief] = []
    vehicle: VehicleBrief | None = None
    weather: dict | None = None
    last_comms_at: str | None = None
    comms_count: int = 0


class ResourceMatch(BaseModel):
    personnel: list[PersonBrief] = []
    vehicles: list[VehicleBrief] = []
    note: str = "stub: same-expedition + readiness/IN_SERVICE filter; real distance tracking is a stretch goal"
