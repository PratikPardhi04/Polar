from pydantic import BaseModel, Field

from app.models.personnel import ReadinessState


class PersonnelCreate(BaseModel):
    full_name: str
    email: str
    phone: str = ""
    role: str = "SCIENTIST"
    expedition_id: str | None = None
    emergency_contact: str = ""


class PersonnelUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None
    expedition_id: str | None = None
    emergency_contact: str | None = None


class ReadinessTransition(BaseModel):
    to_state: ReadinessState
    reason: str = ""


class PersonnelResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: str
    role: str
    expedition_id: str | None
    current_readiness: ReadinessState

    model_config = {"from_attributes": True}


class MovementEvent(BaseModel):
    id: str
    from_state: str | None
    to_state: str
    actor_id: str | None
    reason: str
    created_at: str | None = None

    model_config = {"from_attributes": True}


class ReadinessSummary(BaseModel):
    total: int
    by_state: dict[str, int] = Field(default_factory=dict)
