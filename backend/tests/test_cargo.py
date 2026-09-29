import base64
import re

from app.models.cargo import NORMAL_FLOW
from app.models.station import STATION_SEED, Station


def _seed_stations(db):
    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()


def _token(client, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "Cargo User", "role": role})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _setup(client, db, exp_id: str = "EXP-46ISEA-2026"):
    _seed_stations(db)
    admin = _token(client, f"cargo-{exp_id.lower().replace('_', '-')}-admin@bharati.in", "ADMIN")
    client.post("/api/v1/expeditions", headers=_auth(admin), json={"id": exp_id, "name": "cargo exp", "primary_station_id": "BHARATI"})
    r = client.post("/api/v1/shipments", headers=_auth(admin), json={"expedition_id": exp_id})
    assert r.status_code == 201, r.text
    ship_id = r.json()["id"]
    r = client.post(f"/api/v1/shipments/{ship_id}/containers", headers=_auth(admin), json={})
    container_id = r.json()["id"]
    r = client.post(f"/api/v1/containers/{container_id}/packages", headers=_auth(admin), json={"description": "ice-core kit", "weight_kg": 42.5})
    assert r.status_code == 201, r.text
    pkg = r.json()
    assert re.match(r"^BX-\d+-\d{4}-\d{6}$", pkg["id"]), pkg
    assert base64.b64decode(pkg["qr_code"])[:4] == b"\x89PNG", "QR must be base64 PNG"
    r = client.post(f"/api/v1/packages/{pkg['id']}/items", headers=_auth(admin), json={"name": "ice auger", "quantity": 2, "unit": "pcs", "category": "Tools"})
    assert r.status_code == 201, r.text
    return admin, ship_id, pkg["id"]


def _walk(client, admin: str, kind: str, obj_id: str, stop_before_packed: bool = False, start_after: str | None = None):
    started = start_after is None
    for state in NORMAL_FLOW[1:]:
        if not started:
            if state == start_after:
                started = True
            continue
        if stop_before_packed and state == "PACKED":
            return
        url = f"/api/v1/shipments/{obj_id}/status" if kind == "shipment" else f"/api/v1/packages/{obj_id}/status"
        r = client.patch(url, headers=_auth(admin), json={"to_status": state})
        assert r.status_code == 200, f"{kind} {state}: {r.text}"


def test_shipment_full_walk_with_doc_gate(client, db):
    admin, ship_id, pkg_id = _setup(client, db, exp_id="EXP-90CARGO-2026")
    # DRAFT -> DECLARED -> VERIFIED ok
    _walk(client, admin, "shipment", ship_id, stop_before_packed=True)
    # VERIFIED -> PACKED blocked without docs
    r = client.patch(f"/api/v1/shipments/{ship_id}/status", headers=_auth(admin), json={"to_status": "PACKED"})
    assert r.status_code == 409, r.text
    # generate required docs, then PACKED succeeds
    for dt in ("CARGO_DECLARATION", "PACKING_LIST"):
        r = client.post(f"/api/v1/shipments/{ship_id}/documents/generate", headers=_auth(admin), json={"doc_type": dt})
        assert r.status_code == 201, r.text
    docs = client.get(f"/api/v1/shipments/{ship_id}/documents", headers=_auth(admin)).json()
    assert {d["doc_type"] for d in docs} >= {"CARGO_DECLARATION", "PACKING_LIST"}
    _walk(client, admin, "shipment", ship_id, start_after="VERIFIED")  # PACKED..STORED
    # package walk (no doc gate on packages)
    _walk(client, admin, "package", pkg_id)
    assert client.get(f"/api/v1/packages/{pkg_id}", headers=_auth(admin)).json()["status"] == "STORED"


def test_scan_transition(client, db):
    admin, ship_id, pkg_id = _setup(client, db, exp_id="EXP-91CARGO-2027")
    r = client.post("/api/v1/scan", headers=_auth(admin), json={"package_id": f"POLARIS:{pkg_id}", "to_status": "DECLARED", "location": "Mumbai"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["package"]["location"] == "Mumbai"
    assert body["previous_status"] == "DRAFT"
    # illegal scan skip DECLARED -> STORED
    r = client.post("/api/v1/scan", headers=_auth(admin), json={"package_id": pkg_id, "to_status": "STORED"})
    assert r.status_code == 409, r.text
    # unknown package
    assert client.post("/api/v1/scan", headers=_auth(admin), json={"package_id": "BX-00-0000-000000"}).status_code == 404
