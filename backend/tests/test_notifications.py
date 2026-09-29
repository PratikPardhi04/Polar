from datetime import date, timedelta

from app.models.station import STATION_SEED, Station


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "N User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_stations(db):
    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()


def _unread(client, admin: str, ntype: str | None = None):
    q = "/api/v1/notifications?status=UNREAD" + (f"&notif_type={ntype}" if ntype else "")
    return client.get(q, headers=_auth(admin)).json()


def _mine(rows, entity_id: str):
    return [r for r in rows if r["entity_id"] == entity_id]


def test_stock_crossing_notifies_once(client, db):
    mgr = _token(client, "ntf-mgr@bharati.in", "INVENTORY_MANAGER")
    item = client.post("/api/v1/inventory/items", headers=_auth(mgr), json={"name": "Ntf fuel", "category": "Fuel", "unit": "L", "minimum_stock": 100}).json()
    client.post("/api/v1/inventory/transactions", headers=_auth(mgr), json={"item_id": item["id"], "txn_type": "RECEIVE", "quantity": 500})
    assert _mine(_unread(client, mgr, "STOCK_CRITICAL"), item["id"]) == []
    client.post("/api/v1/inventory/transactions", headers=_auth(mgr), json={"item_id": item["id"], "txn_type": "ISSUE", "quantity": 450})
    rows = _mine(_unread(client, mgr, "STOCK_CRITICAL"), item["id"])
    assert len(rows) == 1 and rows[0]["target_role"] == "INVENTORY_MANAGER" and rows[0]["severity"] == "CRITICAL"
    # further issues while CRITICAL: no duplicate
    client.post("/api/v1/inventory/transactions", headers=_auth(mgr), json={"item_id": item["id"], "txn_type": "ISSUE", "quantity": 10})
    assert len(_mine(_unread(client, mgr, "STOCK_CRITICAL"), item["id"])) == 1
    # read + acknowledge flow
    nid = rows[0]["id"]
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=_auth(mgr)).json()["status"] == "READ"
    assert client.post(f"/api/v1/notifications/{nid}/acknowledge", headers=_auth(mgr)).json()["status"] == "ACKNOWLEDGED"
    assert _mine(_unread(client, mgr, "STOCK_CRITICAL"), item["id"]) == []


def test_missed_and_delayed_notify(client, db):
    admin = _token(client, "ntf-admin@bharati.in", "ADMIN")
    _seed_stations(db)
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": "EXP-46NTF-2026", "name": "ntf", "primary_station_id": "BHARATI"})
    pid = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": "Ntf Op", "email": "ntf-op@bharati.in"}).json()["id"]
    mid = client.post("/api/v1/field-missions", headers=_auth(admin), json={"id": "FM-NTF", "expedition_id": "EXP-46NTF-2026", "leader_id": pid, "check_in_interval_minutes": 60, "grace_minutes": 5, "emergency_kit": True, "emergency_plan": "p"}).json()["id"]
    for state in ("PLANNED", "APPROVED"):
        client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": state})
    client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "DEPLOYED", "override_reason": "test"})
    from datetime import datetime, timezone

    from app.models.checkin import FieldCheckIn

    db.add(FieldCheckIn(mission_id=mid, due_at=datetime.now(timezone.utc) - timedelta(minutes=30)))
    db.commit()
    client.post("/api/v1/check-ins/advance", headers=_auth(admin))
    rows = [r for r in _unread(client, admin, "CHECK_IN_MISSED") if mid in r["message"]]
    assert len(rows) == 1 and rows[0]["target_role"] == "FIELD_LEADER"

    ship = client.post("/api/v1/shipments", headers=_auth(admin), json={"expedition_id": "EXP-46NTF-2026"}).json()
    client.patch(f"/api/v1/shipments/{ship['id']}/status", headers=_auth(admin), json={"to_status": "DELAYED", "reason": "storm at Cape Town"})
    rows = _mine(_unread(client, admin, "CARGO_DELAYED"), ship["id"])
    assert len(rows) == 1 and rows[0]["target_role"] == "LOGISTICS_OFFICER"


def test_sos_and_medical_simulated_alerts(client, db):
    admin = _token(client, "ntf-admin2@bharati.in", "ADMIN")
    _seed_stations(db)
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": "EXP-47NTF-2026", "name": "ntf2", "primary_station_id": "BHARATI"})
    pid = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": "Ntf Sos", "email": "ntf-sos@bharati.in"}).json()["id"]
    mid = client.post("/api/v1/field-missions", headers=_auth(admin), json={"id": "FM-NTF2", "expedition_id": "EXP-47NTF-2026", "leader_id": pid}).json()["id"]

    base_sim = len(client.get("/api/v1/alerts/simulated", headers=_auth(admin)).json())
    r = client.post(
        "/api/v1/sync/events", headers=_auth(admin),
        json={"events": [{"event_id": "ntf-sos-1", "device_id": "T", "user_id": "f", "event_type": "SOS", "entity_id": mid, "timestamp": "2026-03-06T10:00:00Z", "payload": {"personnel_id": pid, "mission_id": mid, "location": "WP-9"}}]},
    )
    assert r.status_code == 200, r.text
    inc_id = r.json()["sos_alerts"][0]["incident_id"]
    assert len(_mine(_unread(client, admin, "SOS"), inc_id)) == 1
    sim = client.get("/api/v1/alerts/simulated", headers=_auth(admin)).json()
    assert len(sim) == base_sim + 2 and all(a["label"] == "SIMULATED" for a in sim)
    assert {a["channel"] for a in sim if a["entity_id"] == inc_id} == {"SMS", "EMAIL"}

    client.post("/api/v1/incidents", headers=_auth(admin), json={"incident_type": "MEDICAL", "personnel_id": pid, "detail": "frostbite"})
    sim2 = client.get("/api/v1/alerts/simulated", headers=_auth(admin)).json()
    assert len(sim2) == base_sim + 4 and any("MEDICAL" in a["subject"] for a in sim2)


def test_maintenance_due_sweep(client, db):
    eng = _token(client, "ntf-eng@bharati.in", "ENGINEER")
    soon = (date.today() + timedelta(days=3)).isoformat()
    client.post("/api/v1/assets", headers=_auth(eng), json={"name": "Ntf genny", "serial_number": "SN-NTF-G1", "next_maintenance": soon})
    rows = _unread(client, eng, "MAINTENANCE_DUE")
    assert len(rows) == 1 and rows[0]["target_role"] == "ENGINEER"
    assert len(_unread(client, eng, "MAINTENANCE_DUE")) == 1  # sweep dedups
