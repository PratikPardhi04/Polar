from datetime import datetime

from pydantic import BaseModel, Field

from app.models.mission import MissionStatus


class MissionCreate(BaseModel):
    id: str | None = Field(default=None, pattern=r"^FM-[A-Z0-9\-]+$", examples=["FM-001"])
    expedition_id: str
    objective: str = ""
    leader_id: str | None = None
    vehicle_id: str | None = None
    equipment_ids: list[str] = Field(default_factory=list)
    start: datetime | None = None
    expected_return: datetime | None = None
    route: str = ""
    check_in_interval_minutes: int = 60
    grace_minutes: int = 15
    emergency_kit: bool = False
    emergency_plan: str = ""


class MissionUpdate(BaseModel):
    objective: str | None = None
    leader_id: str | None = None
    vehicle_id: str | None = None
    equipment_ids: list[str] | None = None
    start: datetime | None = None
    expected_return: datetime | None = None
    route: str | None = None
    check_in_interval_minutes: int | None = None
    grace_minutes: int | None = None
    emergency_kit: bool | None = None
    emergency_plan: str | None = None


class MissionStatusUpdate(BaseModel):
    to_status: MissionStatus
    override_reason: str = ""


class MemberAdd(BaseModel):
    personnel_id: str
    role: str = "MEMBER"


class MemberResponse(BaseModel):
    id: str
    mission_id: str
    personnel_id: str
    role: str

    model_config = {"from_attributes": True}


class MissionResponse(BaseModel):
    id: str
    expedition_id: str
    objective: str
    leader_id: str | None
    vehicle_id: str | None
    equipment_ids: list[str]
    start: datetime | None
    expected_return: datetime | None
    route: str
    check_in_interval_minutes: int
    grace_minutes: int
    emergency_kit: bool
    emergency_plan: str
    status: MissionStatus

    model_config = {"from_attributes": False}


class GoNoGoCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class GoNoGoResponse(BaseModel):
    all_passed: bool
    deploy_allowed: bool
    checks: list[GoNoGoCheck]
