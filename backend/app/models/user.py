import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    EXPEDITION_LEADER = "EXPEDITION_LEADER"
    LOGISTICS_OFFICER = "LOGISTICS_OFFICER"
    INVENTORY_MANAGER = "INVENTORY_MANAGER"
    STATION_LEADER = "STATION_LEADER"
    SCIENTIST = "SCIENTIST"
    FIELD_LEADER = "FIELD_LEADER"
    MEDICAL_OFFICER = "MEDICAL_OFFICER"
    ENGINEER = "ENGINEER"
    DRIVER = "DRIVER"
    EMERGENCY_COORDINATOR = "EMERGENCY_COORDINATOR"
    AUDITOR = "AUDITOR"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False, default="")
    role = Column(Enum(Role, name="user_role", native_enum=False), nullable=False, default=Role.SCIENTIST)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserSession(Base):
    """[ADDED] Session activity log — feeds Phase 7 Audit & Compliance dashboard."""

    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role = Column(String(32), nullable=False)
    login_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_address = Column(String(64), nullable=False, default="simulated")
    user_agent = Column(String(255), nullable=True)
    logout_at = Column(DateTime(timezone=True), nullable=True)
