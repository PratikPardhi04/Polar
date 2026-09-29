from app.models.station import STATION_SEED, Station


def _seed_stations(db):
    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Exp User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_expedition_crud_and_guards(client, db):
    _seed_stations(db)
    admin = _token(client, "exp-admin@bharati.in", "ADMIN")
    sci = _token(client, "exp-sci@bharati.in", "SCIENTIST")

    # scientist write -> 403
    r = client.post("/api/v1/expeditions", headers=_auth(sci), json={"id": "EXP-46ISEA-2026", "name": "46th ISEA", "primary_station_id": "BHARATI"})
    assert r.status_code == 403, r.text

    # admin create with station code
    r = client.post(
        "/api/v1/expeditions",
        headers=_auth(admin),
        json={"id": "EXP-46ISEA-2026", "name": "46th Indian Scientific Expedition to Antarctica", "primary_station_id": "BHARATI", "mission_type": "Polar Environmental Monitoring", "description": "demo focus"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["primary_station"]["code"] == "BHARATI"
    assert r.json()["status"] == "DRAFT"

    # list + get
    assert any(e["id"] == "EXP-46ISEA-2026" for e in client.get("/api/v1/expeditions", headers=_auth(admin)).json())
    r = client.get("/api/v1/expeditions/EXP-46ISEA-2026", headers=_auth(admin))
    assert r.status_code == 200, r.text

    # legal transitions DRAFT -> PLANNED -> ACTIVE
    r = client.patch("/api/v1/expeditions/EXP-46ISEA-2026", headers=_auth(admin), json={"status": "PLANNED"})
    assert r.status_code == 200, r.text
    r = client.patch("/api/v1/expeditions/EXP-46ISEA-2026", headers=_auth(admin), json={"status": "ACTIVE"})
    assert r.status_code == 200, r.text

    # illegal transition ACTIVE -> DRAFT -> 409
    r = client.patch("/api/v1/expeditions/EXP-46ISEA-2026", headers=_auth(admin), json={"status": "DRAFT"})
    assert r.status_code == 409, r.text

    # stations visible (multi-station support)
    codes = {s["code"] for s in client.get("/api/v1/stations", headers=_auth(admin)).json()}
    assert {"BHARATI", "MAITRI", "HIMADRI"} <= codes


def test_unknown_station_400(client, db):
    _seed_stations(db)
    admin = _token(client, "exp-admin2@bharati.in", "ADMIN")
    r = client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": "EXP-TEST-0001", "name": "bad station", "primary_station_id": "NOWHERE"})
    assert r.status_code == 400, r.text
