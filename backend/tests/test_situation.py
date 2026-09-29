from datetime import datetime, timezone

from app.models.station import STATION_SEED, Station


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Sit User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_generate_publish_gates(client, db):
    admin = _token(client, "sit-admin@bharati.in", "ADMIN")
    leader = _token(client, "sit-leader@bharati.in", "STATION_LEADER")
    sci = _token(client, "sit-sci@bharati.in", "SCIENTIST")
    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()

    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": "EXP-46SIT-2026", "name": "sit", "primary_station_id": "BHARATI"})
    pid = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": "Sit Op", "email": "sit-op@bharati.in", "expedition_id": "EXP-46SIT-2026"}).json()["id"]
    client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": "DOCUMENTS_PENDING"})
    item = client.post("/api/v1/inventory/items", headers=_auth(admin), json={"name": "Sit fuel", "category": "Fuel", "unit": "L", "minimum_stock": 50}).json()
    client.post("/api/v1/inventory/transactions", headers=_auth(admin), json={"item_id": item["id"], "txn_type": "RECEIVE", "quantity": 10})
    mid = client.post("/api/v1/field-missions", headers=_auth(admin), json={"id": "FM-SIT", "expedition_id": "EXP-46SIT-2026", "leader_id": pid}).json()["id"]
    inc = client.post("/api/v1/incidents", headers=_auth(admin), json={"incident_type": "EQUIPMENT_FAILURE", "mission_id": mid, "detail": "auger jam"}).json()["id"]

    today = datetime.now(timezone.utc).date().isoformat()
    r = client.post("/api/v1/ai/situation-report/generate", headers=_auth(admin), json={"expedition_id": "EXP-46SIT-2026", "report_date": today})
    assert r.status_code == 201, r.text
    rep = r.json()
    # NEVER auto-published
    assert rep["status"] == "DRAFT" and rep["published_by"] is None
    secs = rep["sections"]
    assert set(secs) == {"personnel", "cargo", "inventory", "field_ops", "incidents", "risks_recommendations"}
    assert secs["personnel"]["total"] == 1 and secs["personnel"]["readiness_changes_today"]
    assert "Sit fuel" in secs["inventory"]["critical"]
    assert any(m["id"] == "FM-SIT" for m in secs["field_ops"]["missions"])
    assert any(i["id"] == inc for i in secs["incidents"]["open"])
    assert any("Sit fuel" in risk for risk in secs["risks_recommendations"])

    rid = rep["id"]
    # scientist cannot publish; station leader can, once
    assert client.post(f"/api/v1/situation-reports/{rid}/publish", headers=_auth(sci)).status_code == 403
    r = client.post(f"/api/v1/situation-reports/{rid}/publish", headers=_auth(leader), json={})
    assert r.status_code == 200 and r.json()["status"] == "PUBLISHED"
    assert client.post(f"/api/v1/situation-reports/{rid}/publish", headers=_auth(leader), json={}).status_code == 409
    assert client.get("/api/v1/situation-reports?status=PUBLISHED", headers=_auth(admin)).json()[0]["id"] == rid
