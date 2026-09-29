from app.models.personnel import READINESS_ORDER
from app.models.station import STATION_SEED, Station
from app.services.personnel_service import can_close_out


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "M User", "role": role})
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


def _walk_readiness(client, admin: str, pid: str, upto: str = "CLOSED_OUT", start_after: str | None = None):
    started = start_after is None
    for state in READINESS_ORDER[1:]:
        if not started:
            if state == start_after:
                started = True
            continue
        r = client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": state})
        assert r.status_code == 200, f"{state}: {r.text}"
        if state == upto:
            break


def _inservice_asset(client, admin: str, name: str, sn: str) -> str:
    aid = client.post("/api/v1/assets", headers=_auth(admin), json={"name": name, "serial_number": sn, "location": "Bharati"}).json()["id"]
    for state in ("RECEIVED", "COMMISSIONED", "IN_SERVICE"):
        client.patch(f"/api/v1/assets/{aid}/status", headers=_auth(admin), json={"to_status": state})
    return aid


def _setup(client, db, exp_id: str, admin: str):
    _seed_stations(db)
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": exp_id, "name": "fm exp", "primary_station_id": "BHARATI"})
    pid = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": "Field Op", "email": f"{exp_id.lower()}-op@bharati.in"}).json()["id"]
    eq = _inservice_asset(client, admin, "Ice radar", f"SN-{exp_id}-EQ")
    asset_id = _inservice_asset(client, admin, "Ski-Doo base", f"SN-{exp_id}-V")
    from app.models.asset import Vehicle  # noqa

    # create vehicle via API (creates its own asset); walk that asset to IN_SERVICE
    veh = client.post("/api/v1/vehicles", headers=_auth(admin), json={"name": "Ski-Doo", "serial_number": f"SN-{exp_id}-VEH"}).json()
    for state in ("RECEIVED", "COMMISSIONED", "IN_SERVICE"):
        client.patch(f"/api/v1/assets/{veh['asset_id']}/status", headers=_auth(admin), json={"to_status": state})
    return pid, eq, veh["id"]


def _make_mission(client, admin: str, exp_id: str, mid: str, pid: str, eq: str, veh: str):
    r = client.post(
        "/api/v1/field-missions",
        headers=_auth(admin),
        json={"id": mid, "expedition_id": exp_id, "objective": "ice-core sampling", "leader_id": pid, "vehicle_id": veh, "equipment_ids": [eq], "emergency_kit": True, "emergency_plan": "sat phone + shelter at waypoint 2"},
    )
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/field-missions/{mid}/members", headers=_auth(admin), json={"personnel_id": pid, "role": "LEADER"})
    assert r.status_code == 201, r.text
    return mid


def test_go_no_go_fail_then_pass_and_deploy(client, db):
    admin = _token(client, "fm-admin@bharati.in", "ADMIN")
    pid, eq, veh = _setup(client, db, "EXP-46FM-2026", admin)
    mid = _make_mission(client, admin, "EXP-46FM-2026", "FM-001", pid, eq, veh)

    # personnel NOMINATED -> check 1 fails
    g = client.post(f"/api/v1/field-missions/{mid}/go-no-go", headers=_auth(admin)).json()
    assert not g["all_passed"] and g["checks"][0]["name"] == "personnel_ready" and not g["checks"][0]["passed"]

    _walk_readiness(client, admin, pid, upto="MISSION_READY")
    g = client.post(f"/api/v1/field-missions/{mid}/go-no-go", headers=_auth(admin)).json()
    assert g["all_passed"], g

    for state in ("PLANNED", "APPROVED", "DEPLOYED"):
        r = client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": state})
        assert r.status_code == 200, f"{state}: {r.text}"
    r = client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "ACTIVE"})
    assert r.status_code == 200, r.text


def test_deploy_blocked_without_override(client, db):
    admin = _token(client, "fm-admin2@bharati.in", "ADMIN")
    sci = _token(client, "fm-sci@bharati.in", "SCIENTIST")
    pid, eq, veh = _setup(client, db, "EXP-47FM-2026", admin)
    mid = _make_mission(client, admin, "EXP-47FM-2026", "FM-002", pid, eq, veh)

    # scientist cannot move status at all
    assert client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(sci), json={"to_status": "PLANNED"}).status_code == 403
    client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "PLANNED"})
    client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "APPROVED"})

    # go/no-go fails (team NOMINATED) -> DEPLOYED without reason blocked
    r = client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "DEPLOYED"})
    assert r.status_code == 409 and "override" in r.json()["detail"].lower()

    # Field Leader override with reason succeeds and logs OVERRIDE
    fl = _token(client, "fm-leader@bharati.in", "FIELD_LEADER")
    r = client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(fl), json={"to_status": "DEPLOYED", "override_reason": "window closing, accepts personnel risk"})
    assert r.status_code == 200, r.text
    rows = db.execute(__import__("sqlalchemy").text("SELECT COUNT(*) FROM audit_events WHERE entity_type='FieldMission' AND action='OVERRIDE'")).first()
    assert rows[0] >= 1


def test_illegal_transition_and_closeout_gate(client, db):
    admin = _token(client, "fm-admin3@bharati.in", "ADMIN")
    pid, eq, veh = _setup(client, db, "EXP-48FM-2026", admin)
    mid = _make_mission(client, admin, "EXP-48FM-2026", "FM-003", pid, eq, veh)

    assert client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": "ACTIVE"}).status_code == 409

    _walk_readiness(client, admin, pid, upto="MISSION_READY")
    for state in ("PLANNED", "APPROVED", "DEPLOYED", "ACTIVE"):
        client.patch(f"/api/v1/field-missions/{mid}/status", headers=_auth(admin), json={"to_status": state})

    # gate is live: member of ACTIVE mission cannot CLOSE_OUT
    ok, why = can_close_out(db, pid)
    assert not ok and "ACTIVE" in why
    _walk_readiness(client, admin, pid, upto="RETURNED", start_after="MISSION_READY")
    r = client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": "CLOSED_OUT"})
    assert r.status_code == 409 and "ACTIVE" in r.json()["detail"]

