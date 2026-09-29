import base64


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Asset User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_asset_lifecycle_walk(client, db):
    eng = _token(client, "asset-eng@bharati.in", "ENGINEER")

    r = client.post("/api/v1/assets", headers=_auth(eng), json={"name": "Ice Auger X1", "serial_number": "SN-2.5-001", "location": "Bharati"})
    assert r.status_code == 201, r.text
    asset = r.json()
    assert asset["status"] == "PROCURED"
    assert base64.b64decode(asset["qr_code"])[:4] == b"\x89PNG"
    aid = asset["id"]

    # illegal skip PROCURED -> IN_SERVICE
    r = client.patch(f"/api/v1/assets/{aid}/status", headers=_auth(eng), json={"to_status": "IN_SERVICE"})
    assert r.status_code == 409, r.text

    for state in ("RECEIVED", "COMMISSIONED", "IN_SERVICE", "MAINTENANCE", "RETURNED_TO_SERVICE", "IN_SERVICE"):
        r = client.patch(f"/api/v1/assets/{aid}/status", headers=_auth(eng), json={"to_status": state})
        assert r.status_code == 200, f"{state}: {r.text}"

    hist = client.get(f"/api/v1/assets/{aid}/history", headers=_auth(eng)).json()
    assert len(hist["transitions"]) >= 6


def test_vehicle_and_work_orders(client, db):
    eng = _token(client, "asset-eng2@bharati.in", "ENGINEER")

    r = client.post("/api/v1/vehicles", headers=_auth(eng), json={"name": "PistenBully 300", "serial_number": "SN-2.5-V001", "registration_number": "ANT-001", "vehicle_type": "Tracked"})
    assert r.status_code == 201, r.text
    assert r.json()["asset"]["asset_type"] == "VEHICLE"
    asset_id = r.json()["asset_id"]

    r = client.post("/api/v1/work-orders", headers=_auth(eng), json={"asset_id": asset_id, "problem": "track tension low", "priority": "HIGH", "assigned_engineer": "eng@bharati.in"})
    assert r.status_code == 201, r.text
    wo_id = r.json()["id"]

    # illegal OPEN -> RESOLVED skip
    r = client.patch(f"/api/v1/work-orders/{wo_id}", headers=_auth(eng), json={"status": "RESOLVED"})
    assert r.status_code == 409, r.text

    for state in ("IN_PROGRESS", "RESOLVED", "CLOSED"):
        payload: dict = {"status": state}
        if state == "RESOLVED":
            payload["resolution"] = "track re-tensioned, tested OK"
        r = client.patch(f"/api/v1/work-orders/{wo_id}", headers=_auth(eng), json=payload)
        assert r.status_code == 200, f"{state}: {r.text}"

    assert any(w["id"] == wo_id for w in client.get("/api/v1/work-orders?status=CLOSED", headers=_auth(eng)).json())


def test_asset_rbac(client, db):
    sci = _token(client, "asset-sci@bharati.in", "SCIENTIST")
    assert client.post("/api/v1/assets", headers=_auth(sci), json={"name": "Nope", "serial_number": "SN-2.5-NOPE"}).status_code == 403
