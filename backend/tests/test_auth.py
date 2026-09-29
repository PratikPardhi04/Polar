from app.models.user import UserSession


def _register(client, email: str, role: str = "SCIENTIST", password: str = "password123"):
    return client.post("/auth/register", json={"email": email, "password": password, "full_name": "Test User", "role": role})


def test_register_login_refresh_rbac(client, db):
    # register scientist
    r = _register(client, "scientist@bharati.in")
    assert r.status_code == 201, r.text

    # duplicate -> 400
    assert _register(client, "scientist@bharati.in").status_code == 400

    # login
    r = client.post("/auth/login", json={"email": "scientist@bharati.in", "password": "password123"})
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    # me
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "scientist@bharati.in"

    # RBAC 403 — scientist hitting admin-only
    r = client.get("/_test/admin-only", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 403, r.text

    # register admin + login, expect 200 on admin-only
    assert _register(client, "admin@bharati.in", role="ADMIN").status_code == 201
    r = client.post("/auth/login", json={"email": "admin@bharati.in", "password": "password123"})
    admin_tokens = r.json()
    r = client.get("/_test/admin-only", headers={"Authorization": f"Bearer {admin_tokens['access_token']}"})
    assert r.status_code == 200, r.text

    # refresh
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]

    # session logged
    assert db.query(UserSession).count() >= 2

    # logout
    r = client.post("/auth/logout", headers={"Authorization": f"Bearer {tokens['access_token']}"}, json={})
    assert r.status_code == 200, r.text


def test_wrong_password_401(client):
    r = client.post("/auth/login", json={"email": "scientist@bharati.in", "password": "wrongpass1"})
    assert r.status_code == 401
