from app.models.inventory import validate_issue


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Inv User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_receive_issue_overissue_rejected(client, db):
    mgr = _token(client, "inv-mgr@bharati.in", "INVENTORY_MANAGER")

    r = client.post(
        "/api/v1/inventory/items",
        headers=_auth(mgr),
        json={"name": "Diesel (polar) 2.4", "category": "Fuel", "unit": "L", "location": "Bharati", "minimum_stock": 100},
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]

    def txn(t, q, **kw):
        return client.post("/api/v1/inventory/transactions", headers=_auth(mgr), json={"item_id": item_id, "txn_type": t, "quantity": q, **kw})

    # RECEIVE 500 -> OK
    assert txn("RECEIVE", 500).status_code == 201
    assert client.get(f"/api/v1/inventory/{item_id}", headers=_auth(mgr)).json()["quantity"] == 500

    # ISSUE 100 -> 400 left
    assert txn("ISSUE", 100, note="generator").status_code == 201
    body = client.get(f"/api/v1/inventory/{item_id}", headers=_auth(mgr)).json()
    assert body["quantity"] == 400 and body["status"] == "OK"

    # over-issue 1000 -> 400 with clear error, quantity unchanged
    r = txn("ISSUE", 1000)
    assert r.status_code == 400, r.text
    assert "insufficient stock" in r.json()["detail"]
    assert client.get(f"/api/v1/inventory/{item_id}", headers=_auth(mgr)).json()["quantity"] == 400

    # drive into WATCH then CRITICAL bands
    assert txn("CONSUME", 250).status_code == 201  # 150 left, min 100 -> WATCH (<=150)
    assert client.get(f"/api/v1/inventory/{item_id}", headers=_auth(mgr)).json()["status"] == "WATCH"
    assert txn("CONSUME", 60).status_code == 201  # 90 left -> CRITICAL
    assert client.get(f"/api/v1/inventory/{item_id}", headers=_auth(mgr)).json()["status"] == "CRITICAL"

    # history shows 4 applied txns (rejected over-issue leaves no row)
    hist = client.get(f"/api/v1/inventory/{item_id}/history", headers=_auth(mgr)).json()
    assert [h["txn_type"] for h in hist] == ["RECEIVE", "ISSUE", "CONSUME", "CONSUME"]

    # low_stock filter surfaces it
    low = client.get("/api/v1/inventory?low_stock=true", headers=_auth(mgr)).json()
    assert any(i["id"] == item_id for i in low)


def test_validate_issue_isolated():
    ok, _ = validate_issue(400, 0, 100)
    assert ok
    ok, msg = validate_issue(400, 50, 400)
    assert not ok and "available 350" in msg
    ok, _ = validate_issue(10, 0, 0)
    assert not ok


def test_inventory_rbac(client, db):
    sci_token = _token(client, "inv-sci@bharati.in", "SCIENTIST")
    r = client.post("/api/v1/inventory/items", headers=_auth(sci_token), json={"name": "Nope"})
    assert r.status_code == 403, r.text
