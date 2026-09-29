from datetime import datetime, timedelta, timezone

from app.models.checkin import FieldCheckIn
from app.models.incident import Incident
from app.models.station import STATION_SEED, Station
from app.services.checkin_service import advance_checkins


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "C User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _setup_active_mission(client, db, exp_id: str, mid: str, admin: str, interval: int = 60, grace: int = 15):
    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": exp_id, "name": "ci exp", "primary_station_id": "BHARATI"})
    pid = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": "Ci Op", "email": f"{exp_id.lower()}-ci@bharati.in"}).json()["id"]
    for state in ("DOCUMENTS_PENDING", "MEDICAL_SCHEDULED", "MEDICAL_CLEARED", "TRAINING_COMPLETED", "MISSION_READY"):
        client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": state})
    r = client.post(
        "/api/v1/field-missions",
        headers=_auth(admin),
        json={"id": mid, "expedition_id": exp_id, "objective": "ci test", "leader_id": pid, "check_in_interval_minutes": interval, "grace_minutes": grace, "emergency_kit": True, "emergency_plan": "plan"},
    )
    assert r.status_code == 201, r.text
    client.post(f"/api/v1/field-missions/{mid}/members", headers=_auth(admin), json={"personnel_id": pid})
    for state in ("PLANNED", "APPROVED"):
        r = client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": state})
        assert r.status_code == 200, f"{state}: {r.text}"
    # no vehicle assigned (foot traverse) -> deploy via Field-Leader-equivalent override
    r = client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "DEPLOYED", "override_reason": "foot traverse, no vehicle required"})
    assert r.status_code == 200, f"DEPLOYED: {r.text}"
    r = client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "ACTIVE"})
    assert r.status_code == 200, f"ACTIVE: {r.text}"
    return pid


def test_check_in_creates_next_due(client, db):
    admin = _token(client, "ci-admin@bharati.in", "ADMIN")
    _setup_active_mission(client, db, "EXP-46CI-2026", "FM-CI1", admin)
    # first check-in opens the cycle (creates DUE); second closes it and schedules next
    assert client.post("/api/v1/field-missions/FM-CI1/check-in", headers=_auth(admin), json={"note": "departed", "location": "Bharati"}).status_code == 201
    r = client.post("/api/v1/field-missions/FM-CI1/check-in", headers=_auth(admin), json={"note": "all ok", "location": "WP-1"})
    assert r.status_code == 201, r.text
    rows = client.get("/api/v1/field-missions/FM-CI1/check-ins", headers=_auth(admin)).json()
    assert [c["status"] for c in rows] == ["CHECKED_IN", "CHECK_IN_DUE"]
    due = datetime.fromisoformat(rows[1]["due_at"])
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    assert timedelta(minutes=55) < (due - datetime.now(timezone.utc)) < timedelta(minutes=65)


def test_missed_pipeline_creates_draft_incident_not_sos(client, db):
    admin = _token(client, "ci-admin2@bharati.in", "ADMIN")
    _setup_active_mission(client, db, "EXP-47CI-2026", "FM-CI2", admin, interval=60, grace=5)
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    db.add(FieldCheckIn(mission_id="FM-CI2", due_at=past))
    db.commit()

    out = advance_checkins(db)
    assert any(m["to"] == "EMERGENCY_ASSESSMENT" for m in out["advanced"]), out
    stages = [m["to"] for m in out["advanced"]]
    assert "MISSED_CHECK_IN" in stages and "LOCAL_ALERT" in stages and "ESCALATION" in stages

    inc = db.query(Incident).filter(Incident.mission_id == "FM-CI2").all()
    assert len(inc) == 1
    t = inc[0].incident_type.value if hasattr(inc[0].incident_type, "value") else str(inc[0].incident_type)
    s = inc[0].status.value if hasattr(inc[0].status, "value") else str(inc[0].status)
    assert (t, s, inc[0].sos_flag) == ("MISSING_PERSON", "OPEN", False)

    # second advance creates no duplicate incident
    advance_checkins(db)
    assert db.query(Incident).filter(Incident.mission_id == "FM-CI2").count() == 1

    # manual trigger endpoint works too
    r = client.post("/api/v1/check-ins/advance", headers=_auth(admin))
    assert r.status_code == 200, r.text


def test_check_in_rejected_when_not_deployed(client, db):
    admin = _token(client, "ci-admin3@bharati.in", "ADMIN")
    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": "EXP-48CI-2026", "name": "ci", "primary_station_id": "BHARATI"})
    client.post("/api/v1/field-missions", headers=_auth(admin), json={"id": "FM-CI3", "expedition_id": "EXP-48CI-2026"})
    r = client.post("/api/v1/field-missions/FM-CI3/check-in", headers=_auth(admin), json={})
    assert r.status_code == 409, r.text


def test_comms_log_roundtrip(client, db):
    admin = _token(client, "ci-admin4@bharati.in", "ADMIN")
    _setup_active_mission(client, db, "EXP-49CI-2026", "FM-CI4", admin)
    for msg in ("Departed Bharati, visibility good.", "WP-1 reached, drilling started."):
        r = client.post("/api/v1/field-missions/FM-CI4/comms", headers=_auth(admin), json={"message": msg})
        assert r.status_code == 201, r.text
    rows = client.get("/api/v1/field-missions/FM-CI4/comms", headers=_auth(admin)).json()
    assert [c["message"] for c in rows] == ["Departed Bharati, visibility good.", "WP-1 reached, drilling started."]
    assert all(c["author"] for c in rows)
    assert client.post("/api/v1/field-missions/FM-CI4/comms", headers=_auth(admin), json={"message": "  "}).status_code == 400
