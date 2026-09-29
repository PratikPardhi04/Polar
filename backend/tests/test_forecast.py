from datetime import datetime, timedelta, timezone

from app.models.inventory import InventoryTransaction


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "F User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_forecast_math_and_sorting(client, db):
    mgr = _token(client, "fc-mgr@bharati.in", "INVENTORY_MANAGER")

    # burner: RECEIVE 100, burn 10/day for 10 days (backdated) -> rate 10/30
    burner = client.post("/api/v1/inventory/items", headers=_auth(mgr), json={"name": "Fc burner fuel", "category": "Fuel", "unit": "L"}).json()
    client.post("/api/v1/inventory/transactions", headers=_auth(mgr), json={"item_id": burner["id"], "txn_type": "RECEIVE", "quantity": 100})
    now = datetime.now(timezone.utc)
    rows = db.query(InventoryTransaction).filter(InventoryTransaction.item_id == burner["id"]).all()
    assert len(rows) == 1  # only RECEIVE so far
    for i in range(10):
        db.add(InventoryTransaction(item_id=burner["id"], txn_type="CONSUME", quantity=10, created_at=now - timedelta(days=i + 1), actor_id="test"))
    db.commit()
    # apply matching quantity change through real transactions is covered elsewhere;
    # set derived level directly here to isolate forecast math from transaction flow
    from app.models.inventory import InventoryItem

    db.query(InventoryItem).filter(InventoryItem.id == burner["id"]).update({"quantity": 40.0})
    db.commit()

    # idle: stock but zero outflow -> rate 0, never at-risk
    idle = client.post("/api/v1/inventory/items", headers=_auth(mgr), json={"name": "Fc idle bolts", "category": "Spare parts"}).json()
    client.post("/api/v1/inventory/transactions", headers=_auth(mgr), json={"item_id": idle["id"], "txn_type": "RECEIVE", "quantity": 5})

    r = client.get("/api/v1/ai/inventory-forecast?window_days=30&lead_time_days=14&safety_days=7", headers=_auth(mgr))
    assert r.status_code == 200, r.text
    items = {i["name"]: i for i in r.json()["items"]}
    b = items["Fc burner fuel"]
    # 100 outflow / 30 days = 3.333/day; reorder = 3.333*14 + 3.333*7 = 70; days = 40/3.333 = 12
    assert b["avg_daily_use"] == 3.333
    assert b["reorder_point"] == 70.0 and b["suggested_reorder_qty"] == 30.0
    assert b["days_until_stockout"] == 12.0 and b["at_risk"] is True
    assert items["Fc idle bolts"]["avg_daily_use"] == 0 and items["Fc idle bolts"]["at_risk"] is False

    # urgency sort: at-risk burner first
    names = [i["name"] for i in r.json()["items"]]
    assert names.index("Fc burner fuel") < names.index("Fc idle bolts")

    # only_at_risk + ewma method
    r = client.get("/api/v1/ai/inventory-forecast?only_at_risk=true&method=ewma", headers=_auth(mgr))
    assert all(i["at_risk"] for i in r.json()["items"]) and r.json()["params"]["method"] == "ewma"
