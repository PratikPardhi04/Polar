from pydantic import BaseModel, Field


class SyncEventIn(BaseModel):
    event_id: str
    device_id: str = ""
    user_id: str = ""
    event_type: str
    entity_id: str = ""
    timestamp: str = ""
    payload: dict = Field(default_factory=dict)


class SyncBatchRequest(BaseModel):
    events: list[SyncEventIn] = Field(max_length=500)


class ConflictResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    event_ids: list[str]
    reason: str
    status: str

    model_config = {"from_attributes": False}


class SyncError(BaseModel):
    event_id: str
    detail: str


class SosAlert(BaseModel):
    incident_id: str
    mission_id: str | None = None
    personnel_id: str | None = None
    escalated: bool = False


class SyncBatchResponse(BaseModel):
    acknowledged: list[str] = Field(default_factory=list)
    conflicts: list[ConflictResponse] = Field(default_factory=list)
    errors: list[SyncError] = Field(default_factory=list)
    sos_alerts: list[SosAlert] = Field(default_factory=list, description="SOS incidents raised/escalated by this batch")


class ConflictResolve(BaseModel):
    resolution: str = Field(pattern=r"^(APPLY_ANYWAY|DISCARD)$")
    note: str = ""
