from app.models.personnel import READINESS_ORDER


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "P User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_full_readiness_walk(client, db):
    admin = _token(client, "pers-admin@bharati.in", "ADMIN")
    r = client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": "Aarav Sharma", "email": "aarav@bharati.in", "role": "SCIENTIST"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["current_readiness"] == "NOMINATED"

    # illegal skip NOMINATED -> MEDICAL_CLEARED -> 409
    r = client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": "MEDICAL_CLEARED"})
    assert r.status_code == 409, r.text

    # full walk incl. [ADDED] tail states
    for state in READINESS_ORDER[1:]:
        r = client.patch(f"/api/v1/personnel/{pid}/readiness", headers=_auth(admin), json={"to_state": state, "reason": f"step to {state}"})
        assert r.status_code == 200, f"{state}: {r.text}"
        assert r.json()["current_readiness"] == state

    # profile + movements + dashboard
    assert client.get(f"/api/v1/personnel/{pid}", headers=_auth(admin)).status_code == 200
    moves = client.get(f"/api/v1/personnel/{pid}/movements", headers=_auth(admin)).json()
    assert len(moves) == len(READINESS_ORDER), moves  # create event + one per step
    summary = client.get("/api/v1/personnel/readiness/summary", headers=_auth(admin)).json()
    assert summary["by_state"].get("CLOSED_OUT", 0) >= 1


def test_personnel_rbac_and_filters(client, db):
    admin = _token(client, "pers-admin2@bharati.in", "ADMIN")
    sci = _token(client, "pers-sci@bharati.in", "SCIENTIST")

    # scientist cannot create -> 403
    r = client.post("/api/v1/personnel", headers=_auth(sci), json={"full_name": "Nope", "email": "nope@bharati.in"})
    assert r.status_code == 403, r.text

    client.post("/api/v1/personnel", headers=_auth(admin), json={"full_name": "Filter Me", "email": "filter@bharati.in"})
    r = client.get("/api/v1/personnel?q=filter", headers=_auth(admin))
    assert r.status_code == 200 and any(p["email"] == "filter@bharati.in" for p in r.json())
    r = client.get("/api/v1/personnel?readiness=NOMINATED", headers=_auth(admin))
    assert r.status_code == 200 and all(p["current_readiness"] == "NOMINATED" for p in r.json())
