from app.models.personnel import READINESS_ORDER
from app.models.station import STATION_SEED, Station


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "I User", "role": role})
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


def _walk(client, admin: str, pid: str, upto: str):
    for state in READINESS_ORDER[1:]:
        r = client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": state})
        assert r.status_code == 200, f"{state}: {r.text}"
        if state == upto:
            break


def _setup(client, db, tag: str, admin: str):
    """Expedition + READY member + deployed standby member + IN_SERVICE vehicle."""
    _seed_stations(db)
    exp = f"EXP-{tag}-2026"
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": exp, "name": "inc exp", "primary_station_id": "BHARATI"})
    victim = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": f"Victim Op {tag}", "email": f"victim-{tag.lower()}@bharati.in"}).json()["id"]
    _walk(client, admin, victim, "MISSION_READY")
    standby = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": f"Standby Op {tag}", "email": f"standby-{tag.lower()}@bharati.in", "expedition_id": exp}).json()["id"]
    _walk(client, admin, standby, "AT_STATION")
    deployed = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": f"Out Op {tag}", "email": f"out-{tag.lower()}@bharati.in", "expedition_id": exp}).json()["id"]
    _walk(client, admin, deployed, "FIELD_DEPLOYED")
    veh = client.post("/api/v1/vehicles", headers=_auth(admin), json={"name": "Rescue Ski-Doo", "serial_number": f"SN-{tag}-V", "registration_number": f"R-{tag}"}).json()
    spare = client.post("/api/v1/vehicles", headers=_auth(admin), json={"name": "Spare Ski-Doo", "serial_number": f"SN-{tag}-S", "registration_number": f"S-{tag}"}).json()
    for aid in (veh["asset_id"], spare["asset_id"]):
        for state in ("RECEIVED", "COMMISSIONED", "IN_SERVICE"):
            client.patch(f"/api/v1/assets/{aid}/status", headers=_auth(admin), json={"to_status": state})
    retired = client.post("/api/v1/assets", headers=_auth(admin), json={"name": "Dead auger", "serial_number": f"SN-{tag}-X"}).json()["id"]
    mid = client.post(
        "/api/v1/field-missions",
        headers=_auth(admin),
        json={"id": f"FM-{tag}", "expedition_id": exp, "objective": "rescue traverse", "leader_id": victim, "vehicle_id": veh["id"], "emergency_kit": True, "emergency_plan": "plan"},
    ).json()["id"]
    client.post(f"/api/v1/field-missions/{mid}/members", headers=_auth(admin), json={"personnel_id": victim})
    for state in ("PLANNED", "APPROVED", "DEPLOYED", "ACTIVE"):
        client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": state})
    client.post(f"/api/v1/field-missions/{mid}/comms", headers=_auth(admin), json={"message": "team radio check, all weak but readable"})
    return exp, victim, standby, deployed, veh["id"], mid


def test_incident_lifecycle_and_detail(client, db):
    admin = _token(client, "inc-admin@bharati.in", "ADMIN")
    exp, victim, standby, deployed, veh, mid = _setup(client, db, "IN1", admin)

    # RBAC: scientist cannot raise incidents
    sci = _token(client, "inc-sci@bharati.in", "SCIENTIST")
    assert client.post("/api/v1/incidents", headers=_auth(sci), json={"incident_type": "MEDICAL"}).status_code == 403

    r = client.post("/api/v1/incidents", headers=_auth(admin), json={"incident_type": "MEDICAL", "personnel_id": victim, "mission_id": mid, "last_location": "WP-2", "detail": "frostbite suspected"})
    assert r.status_code == 201, r.text
    inc_id = r.json()["id"]

    # illegal skip OPEN -> RESPONDING
    assert client.patch(f"/api/v1/incidents/{inc_id}/status", headers=_auth(admin), json={"to_status": "RESPONDING"}).status_code == 409
    for state in ("ASSESSING", "RESPONDING", "RESOLVED", "CLOSED"):
        r = client.patch(f"/api/v1/incidents/{inc_id}/status", headers=_auth(admin), json={"to_status": state})
        assert r.status_code == 200, f"{state}: {r.text}"

    # command-centre detail: person + mission + team + vehicle + comms
    d = client.get(f"/api/v1/incidents/{inc_id}", headers=_auth(admin)).json()
    assert d["person"]["full_name"] == "Victim Op IN1"
    assert d["mission"]["id"] == mid and d["mission"]["status"] == "ACTIVE"
    assert any(t["full_name"] == "Victim Op IN1" for t in d["team"])
    assert d["vehicle"]["asset_status"] == "IN_SERVICE"
    assert d["comms_count"] == 1 and d["last_comms_at"]

    # filters
    assert any(i["id"] == inc_id for i in client.get("/api/v1/incidents?status=CLOSED", headers=_auth(admin)).json())
    assert any(i["id"] == inc_id for i in client.get(f"/api/v1/incidents?mission_id={mid}", headers=_auth(admin)).json())


def test_resource_matching_stub(client, db):
    admin = _token(client, "inc-admin2@bharati.in", "ADMIN")
    exp, victim, standby, deployed, veh, mid = _setup(client, db, "IN2", admin)
    inc_id = client.post("/api/v1/incidents", headers=_auth(admin), json={"incident_type": "VEHICLE_BREAKDOWN", "mission_id": mid, "last_location": "WP-3"}).json()["id"]

    m = client.get(f"/api/v1/incidents/{inc_id}/resources", headers=_auth(admin)).json()
    names = [p["full_name"] for p in m["personnel"]]
    assert "Standby Op IN2" in names, m  # READY + same expedition
    assert "Out Op IN2" not in names  # FIELD_DEPLOYED is not AVAILABLE
    assert "Victim Op IN2" not in names  # on the mission team
    assert any(v["registration_number"] == "S-IN2" for v in m["vehicles"])  # spare IN_SERVICE
    assert not any(v["registration_number"] == "R-IN2" for v in m["vehicles"])  # mission's own vehicle is busy
    assert "stub" in m["note"]
