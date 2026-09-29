from app.models.station import STATION_SEED, Station
from app.services import broadcaster


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "SOS User", "role": role})
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
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": exp, "name": "sos exp", "primary_station_id": "BHARATI"})
    pid = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": f"SOS Op {tag}", "email": f"sos-{tag.lower()}@bharati.in"}).json()["id"]
    mid = client.post("/api/v1/field-missions", headers=_auth(admin), json={"id": f"FM-{tag}", "expedition_id": exp, "objective": "sos traverse", "leader_id": pid, "emergency_kit": True, "emergency_plan": "plan"}).json()["id"]
    return pid, mid


def _sos_event(eid: str, pid: str, mid: str, ts: str):
    return {
        "event_id": eid, "device_id": "FIELD-TABLET-01", "user_id": "field-user", "event_type": "SOS",
        "entity_id": mid, "timestamp": ts,
        "payload": {"personnel_id": pid, "mission_id": mid, "location": "WP-4 Ridge", "battery_pct": 34, "comm_status": "weak-iridium", "team": "2 pax", "expected_return": "2026-03-04T18:00Z", "note": "crevasse fall, leg injury"},
    }


def test_sos_creates_open_flagged_incident(client, db):
    admin = _token(client, "sos-admin@bharati.in", "ADMIN")
    pid, mid = _setup(client, db, "SOS1", admin)

    r = client.post("/api/v1/sync/events", headers=_auth(admin), json={"events": [_sos_event("sos-1", pid, mid, "2026-03-04T10:00:00Z")]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["acknowledged"] == ["sos-1"] and len(body["sos_alerts"]) == 1
    assert body["sos_alerts"][0]["escalated"] is False

    inc = client.get(f"/api/v1/incidents/{body['sos_alerts'][0]['incident_id']}", headers=_auth(admin)).json()
    assert inc["incident"]["status"] == "OPEN" and inc["incident"]["sos_flag"] is True
    assert inc["person"]["full_name"] == "SOS Op SOS1" and inc["mission"]["id"] == mid

    # repeat SOS escalates OPEN -> ASSESSING, same incident
    r = client.post("/api/v1/sync/events", headers=_auth(admin), json={"events": [_sos_event("sos-2", pid, mid, "2026-03-04T10:03:00Z")]})
    alert = r.json()["sos_alerts"][0]
    assert alert["escalated"] is True and alert["incident_id"] == body["sos_alerts"][0]["incident_id"]
    assert client.get(f"/api/v1/incidents/{alert['incident_id']}", headers=_auth(admin)).json()["incident"]["status"] == "ASSESSING"

    # dashboard counts it as open
    assert client.get("/api/v1/dashboard/summary", headers=_auth(admin)).json()["open_incidents"] >= 1


def test_sos_websocket_push(client, db):
    admin = _token(client, "sos-admin2@bharati.in", "ADMIN")
    pid, mid = _setup(client, db, "SOS2", admin)
    # NOTE: same TestClient for WS + HTTP — a second TestClient in this thread deadlocks its portal.
    with client.websocket_connect(f"/api/v1/ws/alerts?token={admin}") as ws:
        assert ws.receive_json()["kind"] == "HELLO"
        r = client.post("/api/v1/sync/events", headers=_auth(admin), json={"events": [_sos_event("sos-ws", pid, mid, "2026-03-05T10:00:00Z")]})
        assert r.status_code == 200, r.text
        msg = ws.receive_json()
        assert msg["kind"] == "SOS" and msg["mission_id"] == mid, msg

    # bad token -> rejected (server closes; handshake or first receive raises)
    try:
        with client.websocket_connect("/api/v1/ws/alerts?token=junk") as ws:
            ws.receive_json()
        rejected = False
    except Exception:
        rejected = True
    assert rejected


def test_broadcaster_unit():
    import anyio

    from app.services import broadcaster as bc

    received: list[dict] = []

    class FakeSocket:
        async def send_json(self, payload: dict):
            received.append(payload)

    async def _run():
        await bc.register(FakeSocket())
        assert await bc.broadcast("SOS", {"incident_id": "x"}) == 1
        assert received[0]["kind"] == "SOS"

    anyio.run(_run)
    assert bc.connection_count() >= 1
