"""Runs the Phase 8.1 demo seed against an ISOLATED sqlite file (never the shared
suite DB) and asserts every spec count. Also asserts idempotent re-runs."""

import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401 — register all tables
from database.seed import seed_demo

DB_PATH = os.path.join(os.path.dirname(__file__), "seed_demo_check.sqlite")


def _fresh_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)()


def test_seed_demo_counts_and_idempotent():
    engine, db = _fresh_db()
    try:
        out = seed_demo.run(db)
        assert out["users"] == 8, out
        assert out["personnel"] == 20, out
        assert out["shipments"] == 3 and out["packages"] == 100, out
        assert out["inventory"] == 50, out
        assert out["assets"] == 30 and out["vehicles"] == 10, out  # 20 equipment + 10 vehicle assets
        assert out["missions"] == 10, out
        assert out["incidents"] == 20 and out["open_incidents"] == 0, out
        assert out["route_legs"] == 4, out

        # readiness mix + mission states + closed reports exist
        from app.models.mission import FieldMission
        from app.models.personnel import Personnel
        from app.models.report import MissionReport

        states = [p.current_readiness.value if hasattr(p.current_readiness, "value") else str(p.current_readiness) for p in db.query(Personnel).all()]
        assert states.count("MISSION_READY") == 18 and "MEDICAL_SCHEDULED" in states and "TRAINING_COMPLETED" in states
        mstates = [m.status.value if hasattr(m.status, "value") else str(m.status) for m in db.query(FieldMission).all()]
        assert mstates.count("DEPLOYED") == 2 and mstates.count("CLOSED") == 2
        assert db.query(MissionReport).count() == 2

        # idempotent re-run changes nothing
        out2 = seed_demo.run(db)
        assert out2 == out, (out, out2)
    finally:
        db.close()
        engine.dispose()
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
