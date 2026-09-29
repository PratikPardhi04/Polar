import os


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Cron User", "role": role})
    return client.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]


def test_advance_cron_secret_gate(client, db, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    admin = _token(client, "cron-admin@bharati.in", "ADMIN")
    h = {"Authorization": f"Bearer {admin}"}

    assert client.post("/api/v1/check-ins/advance-cron").status_code == 403
    assert client.post("/api/v1/check-ins/advance-cron?cron_secret=wrong").status_code == 403
    r = client.post("/api/v1/check-ins/advance-cron?cron_secret=test-cron-secret")
    assert r.status_code == 200 and r.json() == {"advanced": []}, r.text

    # unset secret never matches
    monkeypatch.delenv("CRON_SECRET")
    assert client.post("/api/v1/check-ins/advance-cron?cron_secret=test-cron-secret").status_code == 403
    # role-gated endpoint untouched
    assert client.post("/api/v1/check-ins/advance", headers=h).status_code == 200


def test_vercel_entrypoint_imports():
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
    import importlib

    mod = importlib.import_module("index")
    assert hasattr(mod, "app")
    assert any(getattr(r, "path", "") == "/health" for r in mod.app.routes)
