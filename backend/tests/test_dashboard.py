def test_dashboard_summary(client, db):
    # unauthenticated -> 401/403
    assert client.get("/api/v1/dashboard/summary").status_code in (401, 403)

    client.post("/auth/register", json={"email": "dash-admin@bharati.in", "password": "password123", "full_name": "D", "role": "ADMIN"})
    token = client.post("/auth/login", json={"email": "dash-admin@bharati.in", "password": "password123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # baseline (shared test DB may already hold rows from other test files)
    r = client.get("/api/v1/dashboard/summary", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["expedition"] == "EXP-46ISEA-2026" and body["network"] == "ONLINE"
    base = dict(body)

    # add personnel + critical inventory + in-transit cargo, then re-check
    from app.models.station import STATION_SEED, Station

    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()
    client.post("/api/v1/expeditions", headers=h, json={"id": "EXP-46DASH-2026", "name": "dash", "primary_station_id": "BHARATI"})
    client.post("/api/v1/personnel", headers=h, json={"full_name": "Dash One", "email": "dash1@bharati.in"})
    item = client.post("/api/v1/inventory/items", headers=h, json={"name": "Dash medkit", "category": "Medical", "minimum_stock": 10}).json()
    client.post("/api/v1/inventory/transactions", headers=h, json={"item_id": item["id"], "txn_type": "RECEIVE", "quantity": 5})
    ship = client.post("/api/v1/shipments", headers=h, json={"expedition_id": "EXP-46DASH-2026"}).json()
    for state in ("DECLARED", "VERIFIED"):
        client.patch(f"/api/v1/shipments/{ship['id']}/status", headers=h, json={"to_status": state})
    for dt in ("CARGO_DECLARATION", "PACKING_LIST"):
        client.post(f"/api/v1/shipments/{ship['id']}/documents/generate", headers=h, json={"doc_type": dt})
    for state in ("PACKED", "INSPECTED", "DISPATCHED", "IN_TRANSIT"):
        client.patch(f"/api/v1/shipments/{ship['id']}/status", headers=h, json={"to_status": state})

    body = client.get("/api/v1/dashboard/summary", headers=h).json()
    assert body["personnel_total"] == base["personnel_total"] + 1
    assert body["cargo_in_transit"] == base["cargo_in_transit"] + 1
    assert body["critical_inventory"] == base["critical_inventory"] + 1
