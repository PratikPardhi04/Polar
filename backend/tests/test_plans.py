def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Plan User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_plan_draft_approve_gate(client, db):
    admin = _token(client, "plan-admin@bharati.in", "ADMIN")
    sci = _token(client, "plan-sci@bharati.in", "SCIENTIST")

    # anyone authenticated can draft; nothing executes on create
    r = client.post("/api/v1/plan-drafts", headers=_auth(sci), json={"title": "Reroute via Maitri", "kind": "LOGISTICS", "body": {"action": "hold BX convoy", "reason": "storm"}})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "DRAFT"
    pid = r.json()["id"]

    # scientist cannot approve; admin can, once
    assert client.post(f"/api/v1/plan-drafts/{pid}/decide", headers=_auth(sci), json={"decision": "APPROVE"}).status_code == 403
    r = client.post(f"/api/v1/plan-drafts/{pid}/decide", headers=_auth(admin), json={"decision": "APPROVE", "note": "verified against stock"})
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    assert client.post(f"/api/v1/plan-drafts/{pid}/decide", headers=_auth(admin), json={"decision": "REJECT"}).status_code == 409
    # the human decision is an audited event (Ask POLARIS APPROVE relies on this)
    rows = db.execute(__import__("sqlalchemy").text("SELECT COUNT(*) FROM audit_events WHERE entity_type='PlanDraft' AND action='APPROVE'")).first()
    assert rows[0] >= 1

    # advisories: creatable channel, audited
    r = client.post("/api/v1/notifications", headers=_auth(admin), json={"message": "AI suggests holding convoy", "target_role": "LOGISTICS_OFFICER"})
    assert r.status_code == 201 and r.json()["notif_type"] == "AI_ADVISORY"


def test_reject_spawns_rationed_plan_b(client, db):
    admin = _token(client, "plan-admin2@bharati.in", "ADMIN")

    # AI planner draft with lines -> REJECT spawns a ×0.8 Plan B draft
    body = {"planner": "ai-plan-generator", "lines": [{"item_id": "x", "name": "Rice", "suggested_qty": 100.0, "status": "ORDER NOW", "action": "order"}]}
    did = client.post("/api/v1/plan-drafts", headers=_auth(admin), json={"title": "Food plan", "kind": "INVENTORY", "body": body}).json()["id"]
    r = client.post(f"/api/v1/plan-drafts/{did}/decide", headers=_auth(admin), json={"decision": "REJECT", "note": "too much"})
    assert r.status_code == 200, r.text
    fb_id = r.json()["follow_up_draft_id"]
    assert fb_id and fb_id != did
    drafts = {d["id"]: d for d in client.get("/api/v1/plan-drafts", headers=_auth(admin)).json()}
    assert drafts[fb_id]["status"] == "DRAFT" and "Plan B" in drafts[fb_id]["title"]
    assert drafts[fb_id]["body"]["lines"][0]["suggested_qty"] == 80.0

    # APPROVE never spawns; plain drafts never spawn
    did2 = client.post("/api/v1/plan-drafts", headers=_auth(admin), json={"title": "Plain", "body": {}}).json()["id"]
    assert client.post(f"/api/v1/plan-drafts/{did2}/decide", headers=_auth(admin), json={"decision": "APPROVE"}).json()["follow_up_draft_id"] is None
    did3 = client.post("/api/v1/plan-drafts", headers=_auth(admin), json={"title": "Plain2", "body": {}}).json()["id"]
    assert client.post(f"/api/v1/plan-drafts/{did3}/decide", headers=_auth(admin), json={"decision": "REJECT"}).json()["follow_up_draft_id"] is None
