import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import require_role
from app.database import Base, get_db
from app.main import app as fastapi_app
from app import models as _models  # noqa: F401 — register all tables
from app.models.user import Role

app = fastapi_app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def _override():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override

if not any(getattr(r, "path", None) == "/_test/admin-only" for r in app.routes):

    @app.get("/_test/admin-only")
    def _admin_only(_: object = Depends(require_role(Role.ADMIN))):
        return {"ok": True}


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
