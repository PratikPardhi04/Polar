from datetime import datetime, timezone
from unittest.mock import patch

from app.models.station import STATION_SEED, Station
from app.models.weather import WeatherSnapshot
from app.services.weather_service import evaluate_weather, wmo_to_condition


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "W User", "role": role})
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


def _station_id(db, code: str = "BHARATI") -> str:
    return db.query(Station).filter(Station.code == code).one().id


STATION = "MAITRI"  # isolated from the BHARATI snapshot cached by the endpoint test


def test_wmo_mapping_and_thresholds():
    assert wmo_to_condition(0) == "CLEAR"
    assert wmo_to_condition(71) == "SNOW"
    assert wmo_to_condition(95) == "THUNDERSTORM"
    assert wmo_to_condition(99) == "SEVERE"

    ok, _ = evaluate_weather(WeatherSnapshot(station_id="x", temp_c=-20, wind_kph=30, visibility_m=5000, condition="CLEAR"))
    assert ok
    for bad in [
        {"temp_c": -20, "wind_kph": 90, "visibility_m": 5000, "condition": "CLEAR"},
        {"temp_c": -20, "wind_kph": 30, "visibility_m": 200, "condition": "CLEAR"},
        {"temp_c": -50, "wind_kph": 10, "visibility_m": 5000, "condition": "CLEAR"},
        {"temp_c": -20, "wind_kph": 30, "visibility_m": 5000, "condition": "SEVERE"},
    ]:
        ok, detail = evaluate_weather(WeatherSnapshot(station_id="x", **bad))
        assert not ok and detail.startswith("NO-GO"), bad


def test_weather_endpoint_caches_snapshot(client, db):
    _seed_stations(db)
    admin = _token(client, "wx-admin@bharati.in", "ADMIN")

    fake = {"temp_c": -25.5, "wind_kph": 40.0, "visibility_m": 8000.0, "condition": "CLOUDY"}
    base_count = db.query(WeatherSnapshot).filter(WeatherSnapshot.station_id == _station_id(db)).count()
    with patch("app.routers.weather.fetch_live", return_value=fake):
        r = client.get("/api/v1/weather/BHARATI", headers=_auth(admin))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["station_code"] == "BHARATI" and body["temp_c"] == -25.5 and body["source"] == "LIVE_API"
    assert db.query(WeatherSnapshot).filter(WeatherSnapshot.station_id == _station_id(db)).count() == base_count + 1

    # live API down -> falls back to cached snapshot instead of 503
    with patch("app.routers.weather.fetch_live", side_effect=RuntimeError("no network")):
        r = client.get("/api/v1/weather/BHARATI", headers=_auth(admin))
    assert r.status_code == 200 and r.json()["temp_c"] == -25.5


def test_go_no_go_wired_to_real_thresholds(client, db):
    _seed_stations(db)
    admin = _token(client, "wx-admin2@bharati.in", "ADMIN")
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": "EXP-46WX-2026", "name": "wx", "primary_station_id": STATION})
    pid = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": "Wx Op", "email": "wx-op@bharati.in"}).json()["id"]
    for state in ("DOCUMENTS_PENDING", "MEDICAL_SCHEDULED", "MEDICAL_CLEARED", "TRAINING_COMPLETED", "MISSION_READY"):
        client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": state})
    mid = client.post(
        "/api/v1/field-missions",
        headers=_auth(admin),
        json={"id": "FM-WX", "expedition_id": "EXP-46WX-2026", "objective": "wx test", "leader_id": pid, "emergency_kit": True, "emergency_plan": "plan"},
    ).json()["id"]
    client.post(f"/api/v1/field-missions/{mid}/members", headers=_auth(admin), json={"personnel_id": pid})

    def weather_check():
        g = client.post(f"/api/v1/field-missions/{mid}/go-no-go", headers=_auth(admin)).json()
        return next(c for c in g["checks"] if c["name"] == "weather_acceptable")

    # no snapshot -> passes with pointer to the endpoint
    assert weather_check()["passed"] and STATION in weather_check()["detail"]

    # benign live snapshot -> passes
    db.add(WeatherSnapshot(station_id=_station_id(db, STATION), temp_c=-25, wind_kph=30, visibility_m=9000, condition="CLOUDY", fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    db.commit()
    assert weather_check()["passed"]

    # synthetic severe snapshot (as Simulate Weather Event would push in Phase 8) -> fails
    db.add(WeatherSnapshot(station_id=_station_id(db, STATION), temp_c=-30, wind_kph=95, visibility_m=9000, condition="CLOUDY", fetched_at=datetime(2026, 6, 1, tzinfo=timezone.utc)))
    db.commit()
    c = weather_check()
    assert not c["passed"] and "wind 95" in c["detail"]
