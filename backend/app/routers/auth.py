from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.database import get_db
from app.models.audit import AuditAction, AuditEvent
from app.models.user import User, UserSession
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _audit(db: Session, actor_id: str | None, action: str, entity_type: str, entity_id: str):
    db.add(AuditEvent(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, source="SYNTHETIC_DEMO"))


@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="email already registered")
    user = User(email=body.email.lower(), hashed_password=hash_password(body.password), full_name=body.full_name, role=body.role, is_active=True)
    db.add(user)
    db.flush()
    _audit(db, user.id, AuditAction.CREATE, "User", user.id)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="user inactive")
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    ip = request.client.host if request.client else "simulated"
    db.add(UserSession(user_id=user.id, role=role_val, ip_address=ip or "simulated", user_agent=request.headers.get("user-agent", "test")))
    _audit(db, user.id, AuditAction.LOGIN, "User", user.id)
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, role_val), refresh_token=create_refresh_token(user.id, role_val))


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="refresh token required")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="user not found")
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    return TokenResponse(access_token=create_access_token(user.id, role_val), refresh_token=create_refresh_token(user.id, role_val))


@router.post("/logout")
def logout(body: LogoutRequest | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.logout_at.is_(None)).order_by(UserSession.login_at.desc()).first()
    if session:
        session.logout_at = datetime.now(timezone.utc)
    _audit(db, user.id, AuditAction.LOGOUT, "User", user.id)
    db.commit()
    return {"status": "logged out"}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user
