from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"service": "POLARIS-backend", "status": "ok" if db_ok else "degraded", "db": "up" if db_ok else "down", "expedition": "EXP-46ISEA-2026"}
