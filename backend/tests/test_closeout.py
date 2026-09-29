from datetime import datetime, timedelta, timezone

from app.models.checkin import FieldCheckIn
from app.models.station import STATION_SEED, Station


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Close User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _setup(client, db, tag: str, admin: str):
    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()
    exp = f"EXP-{tag}-2026"
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": exp, "name": "close exp", "primary_station_id": "BHARATI"})
    pid = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": f"Close Op {tag}", "email": f"close-{tag.lower()}@bharati.in", "expedition_id": exp}).json()["id"]
    for state in ("DOCUMENTS_PENDING", "MEDICAL_SCHEDULED", "MEDICAL_CLEARED", "TRAINING_COMPLETED", "MISSION_READY"):
        client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": state})
    eq = client.post("/api/v1/assets", headers=_auth(admin), json={"name": f"Radar {tag}", "serial_number": f"SN-{tag}-EQ"}).json()["id"]
    for state in ("RECEIVED", "COMMISSIONED", "IN_SERVICE"):
        client.patch(f"/api/v1/assets/{eq}/status", headers=_auth(admin), json={"to_status": state})
    veh = client.post("/api/v1/vehicles", headers=_auth(admin), json={"name": f"Ski {tag}", "serial_number": f"SN-{tag}-V", "registration_number": f"CV-{tag}"}).json()
    for state in ("RECEIVED", "COMMISSIONED", "IN_SERVICE"):
        client.patch(f"/api/v1/assets/{veh['asset_id']}/status", headers=_auth(admin), json={"to_status": state})
    mid = client.post(
        "/api/v1/field-missions", headers=_auth(admin),
        json={"id": f"FM-{tag}", "expedition_id": exp, "objective": "closeout traverse", "leader_id": pid, "vehicle_id": veh["id"], "equipment_ids": [eq], "emergency_kit": True, "emergency_plan": "p"},
    ).json()["id"]
    client.post(f"/api/v1/field-missions/{mid}/members", headers=_auth(admin), json={"personnel_id": pid})
    for state in ("PLANNED", "APPROVED"):
        client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": state})
    client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "DEPLOYED"})
    client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "ACTIVE"})
    client.post(f"/api/v1/field-missions/{mid}/check-in", headers=_auth(admin), json={"note": "out"})
    client.post(f"/api/v1/field-missions/{mid}/check-in", headers=_auth(admin), json={"note": "back"})
    client.post(f"/api/v1/field-missions/{mid}/comms", headers=_auth(admin), json={"message": "returning to station"})
    inc = client.post("/api/v1/incidents", headers=_auth(admin), json={"incident_type": "EQUIPMENT_FAILURE", "mission_id": mid, "detail": "auger jam, fixed in field"}).json()["id"]
    for state in ("RETURNED",):
        client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": state})
    return exp, pid, eq, veh, mid, inc


def test_closeout_happy_path_with_report(client, db):
    admin = _token(client, "close-admin@bharati.in", "ADMIN")
    exp, pid, eq, veh, mid, inc = _setup(client, db, "CL1", admin)

    body = {"closing_summary": "cores collected, team back safe", "outcome": "SUCCESS", "vehicle_condition": "RETURNED", "equipment": {eq: "DAMAGED"}}
    r = client.post(f"/api/v1/field-missions/{mid}/close", headers=_auth(admin), json=body)
    assert r.status_code == 201, r.text

    rep = client.get(f"/api/v1/field-missions/{mid}/report", headers=_auth(admin)).json()
    assert rep["mission_status"] == "CLOSED" and rep["outcome"] == "SUCCESS"
    assert "closeout traverse" in rep["html"] and "Close Op CL1" in rep["html"] and inc in rep["html"]
    pdf = client.get(f"/api/v1/field-missions/{mid}/report.pdf", headers=_auth(admin))
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and len(pdf.content) > 1000

    # DAMAGED equipment auto-routed to MAINTENANCE
    assert client.get(f"/api/v1/assets/{eq}", headers=_auth(admin)).json()["status"] == "MAINTENANCE"
    # double close rejected
    assert client.post(f"/api/v1/field-missions/{mid}/close", headers=_auth(admin), json=body).status_code == 409


def test_closeout_gates(client, db):
    admin = _token(client, "close-admin2@bharati.in", "ADMIN")
    exp, pid, eq, veh, mid, inc = _setup(client, db, "CL2", admin)
    good = {"closing_summary": "ok", "outcome": "SUCCESS", "vehicle_condition": "RETURNED", "equipment": {eq: "RETURNED"}}

    # must be RETURNED first (a DRAFT mission cannot close)
    draft = client.post("/api/v1/field-missions", headers=_auth(admin), json={"id": "FM-CL2B", "expedition_id": exp, "objective": "draft"}).json()["id"]
    assert client.post(f"/api/v1/field-missions/{draft}/close", headers=_auth(admin), json=good).status_code == 409

    # summary required
    assert client.post(f"/api/v1/field-missions/{mid}/close", headers=_auth(admin), json={**good, "closing_summary": "  "}).status_code == 400
    # equipment map must cover everything
    assert client.post(f"/api/v1/field-missions/{mid}/close", headers=_auth(admin), json={**good, "equipment": {}}).status_code == 400
    # unaccounted escalation blocks
    db.add(FieldCheckIn(mission_id=mid, due_at=datetime.now(timezone.utc) - timedelta(hours=2)))
    db.commit()
    client.post("/api/v1/check-ins/advance", headers=_auth(admin))
    r = client.post(f"/api/v1/field-missions/{mid}/close", headers=_auth(admin), json=good)
    assert r.status_code == 409 and "unaccounted" in r.json()["detail"]


def test_expedition_phase_report(client, db):
    admin = _token(client, "close-admin3@bharati.in", "ADMIN")
    exp, pid, eq, veh, mid, inc = _setup(client, db, "CL3", admin)
    ship = client.post("/api/v1/shipments", headers=_auth(admin), json={"expedition_id": exp}).json()
    for state in ("DECLARED", "VERIFIED"):
        client.patch(f"/api/v1/shipments/{ship['id']}/status", headers=_auth(admin), json={"to_status": state})
    for dt in ("CARGO_DECLARATION", "PACKING_LIST"):
        client.post(f"/api/v1/shipments/{ship['id']}/documents/generate", headers=_auth(admin), json={"doc_type": dt})
    for state in ("PACKED", "INSPECTED", "DISPATCHED", "IN_TRANSIT", "AT_GATEWAY", "LOADED", "ARRIVED_ANTARCTICA", "RECEIVED_AT_STATION", "STORED"):
        client.patch(f"/api/v1/shipments/{ship['id']}/status", headers=_auth(admin), json={"to_status": state})

    r = client.post(f"/api/v1/expeditions/{exp}/close-phase", headers=_auth(admin), json={"phase_name": "Deployment", "summary": "first wave delivered"})
    assert r.status_code == 201, r.text
    rows = client.get(f"/api/v1/expeditions/{exp}/phase-reports", headers=_auth(admin)).json()
    assert len(rows) == 1
    rollup = rows[0]["rollup"]
    assert rollup["cargo"]["delivered"] == 1 and rollup["personnel"]["total"] == 1 and rollup["incidents"]["total"] == 1
    pdf = client.get(rows[0]["pdf_url"], headers=_auth(admin))
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
