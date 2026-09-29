from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    expedition: str = "EXP-46ISEA-2026"
    station: str = "Bharati"
    personnel_total: int = 0
    readiness_breakdown: dict[str, int] = Field(default_factory=dict)
    cargo_in_transit: int = 0
    packages_in_transit: int = 0
    critical_inventory: int = 0
    watch_inventory: int = 0
    active_field_missions: int = 0
    open_incidents: int = 0
    action_required: int = 0
    network: str = "ONLINE"
