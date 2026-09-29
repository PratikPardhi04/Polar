from app.models.station import STATION_SEED, Station


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "C User", "role": role})
    return client.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]


def test_shipment_children_listing(client, db):
    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()
    admin = _token(client, "kids-admin@bharati.in", "ADMIN")
    h = {"Authorization": f"Bearer {admin}"}
    client.post("/api/v1/expeditions", headers=h, json={"id": "EXP-46KIDS-2026", "name": "kids", "primary_station_id": "BHARATI"})
    ship = client.post("/api/v1/shipments", headers=h, json={"expedition_id": "EXP-46KIDS-2026"}).json()
    c1 = client.post(f"/api/v1/shipments/{ship['id']}/containers", headers=h, json={}).json()
    c2 = client.post(f"/api/v1/shipments/{ship['id']}/containers", headers=h, json={}).json()
    client.post(f"/api/v1/containers/{c1['id']}/packages", headers=h, json={"description": "a"})
    client.post(f"/api/v1/containers/{c2['id']}/packages", headers=h, json={"description": "b"})
    client.post(f"/api/v1/containers/{c2['id']}/packages", headers=h, json={"description": "c"})

    assert len(client.get(f"/api/v1/shipments/{ship['id']}/containers", headers=h).json()) == 2
    assert len(client.get(f"/api/v1/shipments/{ship['id']}/packages", headers=h).json()) == 3
    assert client.get("/api/v1/shipments/nope/containers", headers=h).status_code == 404
