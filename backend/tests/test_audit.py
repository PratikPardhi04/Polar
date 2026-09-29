def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Audit User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_audit_filters_search_export(client, db):
    from app.models.station import STATION_SEED, Station

    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()
    admin = _token(client, "audit-admin@bharati.in", "ADMIN")
    # generate traceable events: expedition + personnel transition + failed login
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": "EXP-46AUD-2026", "name": "audit exp", "primary_station_id": "BHARATI"})
    pid = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": "Audit Op", "email": "audit-op@bharati.in"}).json()["id"]
    client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": "DOCUMENTS_PENDING"})
    client.post("/auth/login", json={"email": "audit-admin@bharati.in", "password": "wrongpass1"})

    base = "/api/v1/audit/events"
    all_rows = client.get(base, headers=_auth(admin)).json()
    assert len(all_rows) >= 4

    # entity filter: everything touching this person
    mine = client.get(f"{base}?entity_type=Personnel&entity_id={pid}", headers=_auth(admin)).json()
    assert len(mine) == 2 and {r["action"] for r in mine} == {"CREATE", "STATUS_TRANSITION"}

    # action + actor filters
    assert len(client.get(f"{base}?action=LOGIN", headers=_auth(admin)).json()) >= 1
    assert any("audit-admin@bharati.in" in (r["actor_email"] or "") for r in client.get(f"{base}?actor=audit-admin", headers=_auth(admin)).json())

    # search box: expedition id fragment
    assert any(r["entity_id"] == "EXP-46AUD-2026" for r in client.get(f"{base}?search=46AUD", headers=_auth(admin)).json())

    # date range: future since -> empty
    assert client.get(f"{base}?since=2099-01-01T00:00:00", headers=_auth(admin)).json() == []

    # CSV export honours filters
    r = client.get(f"{base}/export?entity_id={pid}", headers=_auth(admin))
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("id,created_at,actor") and len(lines) == 3

    # sessions table is visible too
    sessions = client.get("/api/v1/audit/sessions", headers=_auth(admin)).json()
    assert any(s["user_email"] == "audit-admin@bharati.in" for s in sessions)

    # unauthenticated -> rejected
    assert client.get(base).status_code in (401, 403)
