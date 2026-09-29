import os

from app.models.station import STATION_SEED, Station


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Sim User", "role": role})
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


def _setup(client, db, tag: str, admin: str):
    _seed_stations(db)
    exp = f"EXP-{tag}-2026"
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": exp, "name": "sim exp", "primary_station_id": "BHARATI"})
    ship = client.post("/api/v1/shipments", headers=_auth(admin), json={"expedition_id": exp}).json()
    for state in ("DECLARED", "VERIFIED"):
        client.patch(f"/api/v1/shipments/{ship['id']}/status", headers=_auth(admin), json={"to_status": state})
    for dt in ("CARGO_DECLARATION", "PACKING_LIST"):
        client.post(f"/api/v1/shipments/{ship['id']}/documents/generate", headers=_auth(admin), json={"doc_type": dt})
    for state in ("PACKED", "INSPECTED", "DISPATCHED", "IN_TRANSIT"):
        client.patch(f"/api/v1/shipments/{ship['id']}/status", headers=_auth(admin), json={"to_status": state})
    pid = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": f"Sim Op {tag}", "email": f"sim-{tag.lower()}@bharati.in"}).json()["id"]
    for state in ("DOCUMENTS_PENDING", "MEDICAL_SCHEDULED", "MEDICAL_CLEARED", "TRAINING_COMPLETED", "MISSION_READY"):
        client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": state})
    mid = client.post("/api/v1/field-missions", headers=_auth(admin), json={"id": f"FM-{tag}", "expedition_id": exp, "leader_id": pid, "emergency_kit": True, "emergency_plan": "p"}).json()["id"]
    for state in ("PLANNED", "APPROVED"):
        client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": state})
    client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "DEPLOYED", "override_reason": "sim setup"})
    client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "ACTIVE"})
    item = client.post("/api/v1/inventory/items", headers=_auth(admin), json={"name": f"Sim diesel {tag}", "category": "Fuel", "unit": "L", "minimum_stock": 10}).json()
    client.post("/api/v1/inventory/transactions", headers=_auth(admin), json={"item_id": item["id"], "txn_type": "RECEIVE", "quantity": 100})
    return ship["id"], pid, mid, item["id"]


def test_simulation_panel_end_to_end(client, db):
    admin = _token(client, "sim-admin@bharati.in", "ADMIN")
    sci = _token(client, "sim-sci@bharati.in", "SCIENTIST")
    ship_id, pid, mid, item_id = _setup(client, db, "SIM1", admin)
    base = "/api/v1/simulate"

    # RBAC: scientists get 403 everywhere
    for path, body in [("/cargo-delay", {}), ("/network-outage", {"online": False}), ("/missed-check-in", {}), ("/sos", {}), ("/inventory-shortage", {}), ("/weather-event", {})]:
        assert client.post(f"{base}{path}", headers=_auth(sci), json=body).status_code == 403

    # 1. cargo delay through the real machine (+ notification)
    r = client.post(f"{base}/cargo-delay", headers=_auth(admin), json={"shipment_id": ship_id})
    assert r.status_code == 200 and r.json()["status"] == "DELAYED", r.text
    assert any(n["entity_id"] == ship_id for n in client.get("/api/v1/notifications?notif_type=CARGO_DELAYED", headers=_auth(admin)).json())

    # 2. network outage flag flips dashboard (reset in finally)
    try:
        assert client.post(f"{base}/network-outage", headers=_auth(admin), json={"online": False}).json()["network"] == "OFFLINE"
        assert client.get("/api/v1/dashboard/summary", headers=_auth(admin)).json()["network"] == "OFFLINE"
    finally:
        client.post(f"{base}/network-outage", headers=_auth(admin), json={"online": True})
    assert client.get("/api/v1/dashboard/summary", headers=_auth(admin)).json()["network"] == "ONLINE"

    # 3. missed check-in escalates to a draft incident
    r = client.post(f"{base}/missed-check-in", headers=_auth(admin), json={"mission_id": mid})
    assert r.status_code == 200 and any(m["to"] == "MISSED_CHECK_IN" for m in r.json()["advanced"]), r.text
    assert any(i["mission_id"] == mid for i in client.get("/api/v1/incidents?status=OPEN", headers=_auth(admin)).json())

    # 4. SOS creates a flagged incident
    r = client.post(f"{base}/sos", headers=_auth(admin), json={"mission_id": mid, "personnel_id": pid})
    assert r.status_code == 200 and len(r.json()["sos_alerts"]) == 1, r.text
    inc_id = r.json()["sos_alerts"][0]["incident_id"]
    assert client.get(f"/api/v1/incidents/{inc_id}", headers=_auth(admin)).json()["incident"]["sos_flag"] is True

    # 5. shortage drives the item CRITICAL
    r = client.post(f"{base}/inventory-shortage", headers=_auth(admin), json={"item_id": item_id})
    assert r.status_code == 200 and r.json()["status"] == "CRITICAL", r.text

    # 6. weather event fails Go/No-Go + notifies
    r = client.post(f"{base}/weather-event", headers=_auth(admin), json={"station": "BHARATI"})
    assert r.status_code == 200, r.text
    g = client.post(f"/api/v1/field-missions/{mid}/go-no-go", headers=_auth(admin)).json()
    wx = next(c for c in g["checks"] if c["name"] == "weather_acceptable")
    assert wx["passed"] is False
    assert len(client.get("/api/v1/notifications?notif_type=WEATHER_ALERT", headers=_auth(admin)).json()) >= 1

    # audit trail captured the simulations
    assert len(client.get("/api/v1/audit/events?search=SIMULAT", headers=_auth(admin)).json()) >= 3
