from app.models.station import STATION_SEED, Station


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Sync User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _issue_event(eid: str, item_name: str, qty: float, ts: str):
    return {"event_id": eid, "device_id": "FIELD-TABLET-01", "user_id": "field-user", "event_type": "INVENTORY_ISSUE", "entity_id": item_name, "timestamp": ts, "payload": {"item": item_name, "quantity": qty, "unit": "L"}}


def test_offline_issues_apply_in_order(client, db):
    mgr = _token(client, "sync-mgr@bharati.in", "INVENTORY_MANAGER")
    item = client.post("/api/v1/inventory/items", headers=_auth(mgr), json={"name": "Sync diesel 3.2", "category": "Fuel", "unit": "L"}).json()
    client.post("/api/v1/inventory/transactions", headers=_auth(mgr), json={"item_id": item["id"], "txn_type": "RECEIVE", "quantity": 100})

    batch = {"events": [_issue_event("sync-e1", "Sync diesel 3.2", 30, "2026-03-01T10:00:00Z"), _issue_event("sync-e2", "Sync diesel 3.2", 30, "2026-03-01T10:05:00Z")]}
    r = client.post("/api/v1/sync/events", headers=_auth(mgr), json=batch)
    assert r.status_code == 200, r.text
    assert sorted(r.json()["acknowledged"]) == ["sync-e1", "sync-e2"]
    assert r.json()["conflicts"] == [] and r.json()["errors"] == []
    assert client.get(f"/api/v1/inventory/{item['id']}", headers=_auth(mgr)).json()["quantity"] == 40

    # idempotent re-upload: ACKed again, stock NOT double-applied
    r = client.post("/api/v1/sync/events", headers=_auth(mgr), json=batch)
    assert sorted(r.json()["acknowledged"]) == ["sync-e1", "sync-e2"]
    assert client.get(f"/api/v1/inventory/{item['id']}", headers=_auth(mgr)).json()["quantity"] == 40


def test_combined_overissue_creates_conflict(client, db):
    mgr = _token(client, "sync-mgr2@bharati.in", "INVENTORY_MANAGER")
    item = client.post("/api/v1/inventory/items", headers=_auth(mgr), json={"name": "Sync kerosene 3.2", "category": "Fuel", "unit": "L"}).json()
    client.post("/api/v1/inventory/transactions", headers=_auth(mgr), json={"item_id": item["id"], "txn_type": "RECEIVE", "quantity": 40})

    # each issue fits alone (30 <= 40) but combined 60 > 40 -> NEITHER applied, ONE conflict
    batch = {"events": [_issue_event("sync-c1", "Sync kerosene 3.2", 30, "2026-03-02T10:00:00Z"), _issue_event("sync-c2", "Sync kerosene 3.2", 30, "2026-03-02T10:01:00Z")]}
    r = client.post("/api/v1/sync/events", headers=_auth(mgr), json=batch)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["acknowledged"] == [] and len(body["conflicts"]) == 1
    assert client.get(f"/api/v1/inventory/{item['id']}", headers=_auth(mgr)).json()["quantity"] == 40

    # ACTION REQUIRED surfaces it
    assert client.get("/api/v1/dashboard/summary", headers=_auth(mgr)).json()["action_required"] == 1
    conflicts = client.get("/api/v1/sync/conflicts", headers=_auth(mgr)).json()
    assert len(conflicts) == 1 and conflicts[0]["status"] == "OPEN"

    # DISCARD resolves without touching stock
    cid = conflicts[0]["id"]
    r = client.post(f"/api/v1/sync/conflicts/{cid}/resolve", headers=_auth(mgr), json={"resolution": "DISCARD", "note": "field re-counted"})
    assert r.status_code == 200 and r.json()["status"] == "RESOLVED"
    assert client.get(f"/api/v1/inventory/{item['id']}", headers=_auth(mgr)).json()["quantity"] == 40
    assert client.get("/api/v1/dashboard/summary", headers=_auth(mgr)).json()["action_required"] == 0


def test_cargo_scan_sync_updates_location(client, db):
    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()
    admin = _token(client, "sync-admin@bharati.in", "ADMIN")
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": "EXP-46SYNC-2026", "name": "sync", "primary_station_id": "BHARATI"})
    ship = client.post("/api/v1/shipments", headers=_auth(admin), json={"expedition_id": "EXP-46SYNC-2026"}).json()
    cont = client.post(f"/api/v1/shipments/{ship['id']}/containers", headers=_auth(admin), json={}).json()
    pkg = client.post(f"/api/v1/containers/{cont['id']}/packages", headers=_auth(admin), json={"description": "sync box"}).json()

    r = client.post(
        "/api/v1/sync/events",
        headers=_auth(admin),
        json={"events": [{"event_id": "sync-scan1", "device_id": "FIELD-TABLET-01", "user_id": "f", "event_type": "CARGO_SCANNED", "entity_id": pkg["id"], "timestamp": "2026-03-03T10:00:00Z", "payload": {"package_id": pkg["id"], "location": "Cape Town"}}]},
    )
    assert r.json()["acknowledged"] == ["sync-scan1"], r.text
    assert client.get(f"/api/v1/packages/{pkg['id']}", headers=_auth(admin)).json()["location"] == "Cape Town"

    # unknown item -> per-event error, not a 500
    r = client.post("/api/v1/sync/events", headers=_auth(admin), json={"events": [_issue_event("sync-err1", "No such item", 5, "2026-03-03T11:00:00Z")]})
    assert len(r.json()["errors"]) == 1 and r.json()["acknowledged"] == []
