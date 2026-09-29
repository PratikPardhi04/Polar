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
