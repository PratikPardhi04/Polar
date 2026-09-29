"""POLARIS backend models package. All tables must emit AuditEvent on state transitions (Phase 7 UI reads this)."""
from app.database import Base  # noqa: F401
from app.models.audit import AuditEvent  # noqa: F401
from app.models.asset import Asset, MaintenanceWorkOrder, Vehicle  # noqa: F401
from app.models.cargo import CargoItem, Container, DocType, Document, Package, Shipment  # noqa: F401
from app.models.checkin import FieldCheckIn, MissionComms  # noqa: F401
from app.models.expedition import DataSource, Expedition, ExpeditionStatus  # noqa: F401
from app.models.incident import Incident  # noqa: F401
from app.models.inventory import InventoryItem, InventoryTransaction  # noqa: F401
from app.models.mission import FieldMission, FieldMissionMember  # noqa: F401
from app.models.notification import Notification, SimulatedAlert  # noqa: F401
from app.models.plan import PlanDraft  # noqa: F401
from app.models.report import MissionReport, PhaseReport  # noqa: F401
from app.models.route_leg import RouteLeg  # noqa: F401
from app.models.situation import SituationReport  # noqa: F401
from app.models.sync import SyncConflict, SyncedEvent  # noqa: F401
from app.models.weather import WeatherSnapshot  # noqa: F401
from app.models.personnel import Personnel, PersonnelReadinessEvent, ReadinessState  # noqa: F401
from app.models.station import Station  # noqa: F401
from app.models.user import Role, User, UserSession  # noqa: F401
