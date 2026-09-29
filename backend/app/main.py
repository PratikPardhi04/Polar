import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app.config import settings
from app.routers.ai import router as ai_router
from app.routers.alerts_ws import router as alerts_ws_router
from app.routers.audit import router as audit_router
from app.routers.assets import router as assets_router
from app.routers.auth import router as auth_router
from app.routers.cargo import router as cargo_router
from app.routers.checkins import router as checkins_router
from app.routers.closeout import router as closeout_router
from app.routers.dashboard import router as dashboard_router
from app.routers.expeditions import router as expeditions_router
from app.routers.health import router as health_router
from app.routers.incidents import router as incidents_router
from app.routers.inventory import router as inventory_router
from app.routers.missions import router as missions_router
from app.routers.notifications import router as notifications_router
from app.routers.personnel import router as personnel_router
from app.routers.plans import router as plans_router
from app.routers.route import router as route_router
from app.routers.simulate import router as simulate_router
from app.routers.situation import generate_router as situation_generate_router
from app.routers.situation import reports_router as situation_reports_router
from app.routers.sync import router as sync_router
from app.routers.weather import router as weather_router


def _checkin_tick():
    from app.database import SessionLocal
    from app.services.checkin_service import advance_checkins

    db = SessionLocal()
    try:
        advance_checkins(db)
    except Exception:
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Serverless hosts (Vercel) have no long-lived process: skip the in-process
    # scheduler there (Vercel sets VERCEL=1) and drive escalation via Vercel Cron
    # → POST /api/v1/check-ins/advance-cron instead. See docs/deployment.md.
    if os.getenv("VERCEL"):
        yield
        return
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_checkin_tick, "interval", minutes=1, id="checkin-escalation")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="POLARIS — Polar Expedition Logistics", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts_ws_router)
app.include_router(ai_router)
app.include_router(audit_router)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(assets_router)
app.include_router(expeditions_router)
app.include_router(cargo_router)
app.include_router(checkins_router)
app.include_router(closeout_router)
app.include_router(dashboard_router)
app.include_router(incidents_router)
app.include_router(inventory_router)
app.include_router(missions_router)
app.include_router(notifications_router)
app.include_router(personnel_router)
app.include_router(plans_router)
app.include_router(route_router)
app.include_router(simulate_router)
app.include_router(situation_generate_router)
app.include_router(situation_reports_router)
app.include_router(sync_router)
app.include_router(weather_router)


@app.get("/")
def root():
    return {"app": settings.APP_NAME, "expedition": "EXP-46ISEA-2026", "station": "Bharati", "docs": "/docs"}
