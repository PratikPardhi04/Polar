"""Synthetic demo seed (Phase 8.1). Everything tagged source=SYNTHETIC_DEMO.

Covers: 8 users, 3 stations (via seed_phase2 data), EXP-46ISEA-2026, 20 personnel,
3 shipments / 15 containers / 100 packages (+ docs), 50 inventory items,
20 assets, 10 vehicles, 10 field missions (2 DEPLOYED, 2 CLOSED with reports),
20 CLOSED incidents (0 open), 4 route legs.

Idempotent per section: re-runs skip what already exists.
Run:  DATABASE_URL=postgresql+psycopg2://polaris:polaris@localhost:5432/polaris
       python seed_demo.py   (from database/seed/, backend/ on PYTHONPATH)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.models.asset import Asset
from app.models.cargo import NORMAL_FLOW, CargoStatus
from app.models.expedition import DataSource, Expedition, ExpeditionStatus
from app.models.inventory import CATEGORIES
from app.models.mission import FieldMission, FieldMissionMember
from app.models.route_leg import LegStatus, RouteLeg
from app.models.station import STATION_SEED, Station
from app.models.user import Role, User
from app.services import (
    asset_service,
    cargo_service,
    checkin_service,
    closeout_service,
    expedition_service,
    incident_service,
    inventory_service,
    mission_service,
    personnel_service,
)
from app.schemas.asset import AssetCreate, VehicleCreate
from app.schemas.expedition import ExpeditionCreate
from app.schemas.incident import IncidentCreate
from app.schemas.inventory import ItemCreate as InvItemCreate
from app.schemas.mission import MissionCreate
from app.schemas.personnel import PersonnelCreate

EXP_ID = "EXP-46ISEA-2026"
ACTOR = {"actor_id": "seed"}

NAMES = [
    ("Aarav Sharma", "SCIENTIST"), ("Diya Patel", "SCIENTIST"), ("Arjun Nair", "ENGINEER"),
    ("Meera Iyer", "MEDICAL_OFFICER"), ("Kabir Singh", "FIELD_LEADER"), ("Ananya Das", "SCIENTIST"),
    ("Vikram Rao", "ENGINEER"), ("Ishita Bose", "SCIENTIST"), ("Rohan Mehta", "DRIVER"),
    ("Priya Nambiar", "SCIENTIST"), ("Aditya Kulkarni", "ENGINEER"), ("Sneha Reddy", "MEDICAL_OFFICER"),
    ("Karan Malhotra", "DRIVER"), ("Divya Menon", "SCIENTIST"), ("Nikhil Joshi", "ENGINEER"),
    ("Pooja Desai", "SCIENTIST"), ("Rahul Verma", "DRIVER"), ("Kavya Pillai", "SCIENTIST"),
    ("Sanjay Gupta", "LOGISTICS_OFFICER"), ("Ritu Saxena", "SCIENTIST"),
]
READINESS_WALK = ["DOCUMENTS_PENDING", "MEDICAL_SCHEDULED", "MEDICAL_CLEARED", "TRAINING_COMPLETED", "MISSION_READY"]

USERS = [
    ("admin@bharati.in", "ADMIN"), ("leader@bharati.in", "EXPEDITION_LEADER"),
    ("logistics@bharati.in", "LOGISTICS_OFFICER"), ("inventory@bharati.in", "INVENTORY_MANAGER"),
    ("station@bharati.in", "STATION_LEADER"), ("field@bharati.in", "FIELD_LEADER"),
    ("engineer@bharati.in", "ENGINEER"), ("emergency@bharati.in", "EMERGENCY_COORDINATOR"),
]

STOCK = [
    ("Food", [("Rice", 500, "kg", 100), ("Dal", 300, "kg", 60), ("Freeze-dried meals", 400, "pcs", 80), ("Cooking oil", 120, "L", 20), ("Tea", 60, "kg", 40)]),
    ("Fuel", [("Diesel (polar)", 2000, "L", 400), ("Kerosene", 800, "L", 150), ("Petrol", 300, "L", 280), ("LPG cylinders", 40, "cyl", 10), ("Grease", 90, "kg", 20)]),
    ("Medical", [("Medkit A", 25, "pcs", 5), ("Antibiotics", 200, "pcs", 40), ("Bandages", 500, "pcs", 100), ("Oxygen cylinders", 12, "cyl", 4), ("Vaccines", 60, "pcs", 55)]),
    ("Batteries", [("AA cells", 1000, "pcs", 200), ("Li-ion packs", 120, "pcs", 30), ("UPS batteries", 20, "pcs", 6), ("Solar batteries", 30, "pcs", 28), ("Torch cells", 400, "pcs", 80)]),
    ("Scientific supplies", [("Sample vials", 2000, "pcs", 400), ("Filters", 600, "pcs", 120), ("Reagents", 150, "pcs", 140), ("Thermometers", 40, "pcs", 8), ("Core boxes", 300, "pcs", 60)]),
    ("Safety equipment", [("Harnesses", 40, "pcs", 8), ("Helmets", 45, "pcs", 10), ("Flares", 100, "pcs", 90), ("Life vests", 35, "pcs", 8), ("Fire extinguishers", 24, "pcs", 6)]),
    ("Tools", [("Wrenches", 60, "pcs", 12), ("Drills", 18, "pcs", 4), ("Shovels", 50, "pcs", 45), ("Saws", 22, "pcs", 5), ("Multimeters", 15, "pcs", 3)]),
    ("Spare parts", [("Track links", 80, "pcs", 16), ("Engine belts", 45, "pcs", 40), ("Fuses", 500, "pcs", 100), ("Bearings", 120, "pcs", 25), ("Hydraulic hose", 30, "pcs", 6)]),
    ("Cold-weather gear", [("Parkas", 60, "pcs", 12), ("Gloves", 120, "pcs", 25), ("Boots", 55, "pcs", 50), ("Goggles", 70, "pcs", 15), ("Sleeping bags", 45, "pcs", 10)]),
    ("Communication", [("Iridium handsets", 14, "pcs", 3), ("VHF radios", 30, "pcs", 6), ("Antennas", 20, "pcs", 18), ("Cables", 200, "pcs", 40), ("Repeaters", 8, "pcs", 2)]),
]

ASSETS = ["Diesel Generator A", "Diesel Generator B", "Water Desalinator", "Met Mast", "Ice Radar", "Drill Rig", "Crane", "Forklift", "Fuel Bowser", "Workshop Lathe", "Compressor", "Heater Unit", "Water Tank", "Solar Array", "Wind Turbine", "Satellite Dish", "Server Rack", "Lab Freezer", "Incinerator", "Snow Blower"]
VEHICLES = [("Ski-Doo", 6), ("PistenBully", 2), ("Hilux", 2)]
INCIDENT_TYPES = ["MEDICAL", "VEHICLE_BREAKDOWN", "EQUIPMENT_FAILURE", "EXTREME_WEATHER", "FUEL_SPILL", "COMMUNICATION_FAILURE", "FIRE", "ENVIRONMENTAL_INCIDENT", "MISSING_PERSON"]


def seed_users(db: Session):
    for email, role in USERS:
        if not db.query(User).filter(User.email == email).first():
            db.add(User(email=email, hashed_password=hash_password("polaris123"), full_name=role.title(), role=Role(role), is_active=True))
    db.commit()
    return db.query(User).filter(User.email == "admin@bharati.in").one().id


def seed_stations(db: Session):
    for seed in STATION_SEED:
        if not db.query(Station).filter(Station.code == seed["code"]).first():
            db.add(Station(**seed))
    db.commit()


def seed_expedition(db: Session, admin_id: str):
    exp = db.query(Expedition).filter(Expedition.id == EXP_ID).first()
    if not exp:
        expedition_service.create_expedition(
            db, ExpeditionCreate(id=EXP_ID, name="46th Indian Scientific Expedition to Antarctica", primary_station_id="BHARATI", mission_type="Polar Environmental Monitoring", description="Demo expedition — Bharati station focus", source=DataSource.SYNTHETIC_DEMO), actor_id=admin_id,
        )
        exp = db.query(Expedition).filter(Expedition.id == EXP_ID).first()
    from app.models.expedition import ExpeditionStatus
    from app.schemas.expedition import ExpeditionUpdate

    order = [ExpeditionStatus.DRAFT, ExpeditionStatus.PLANNED, ExpeditionStatus.ACTIVE]
    cur = exp.status.value if hasattr(exp.status, "value") else str(exp.status)
    start = ([s.value for s in order].index(cur) + 1) if cur in [s.value for s in order] else 0
    for to in order[start:]:
        expedition_service.patch_expedition(db, exp, ExpeditionUpdate(status=to), actor_id=admin_id)


def seed_personnel(db: Session, admin_id: str):
    have = db.query(personnel_service.Personnel).count()
    if have >= 20:
        return [p.id for p in db.query(personnel_service.Personnel).order_by(personnel_service.Personnel.full_name).limit(20).all()]
    ids = []
    for i, (name, role) in enumerate(NAMES):
        email = f"{name.lower().replace(' ', '.')}@bharati.in"
        person = db.query(personnel_service.Personnel).filter(personnel_service.Personnel.email == email).first()
        if not person:
            person = personnel_service.create_personnel(db, PersonnelCreate(full_name=name, email=email, role=role, expedition_id=EXP_ID), actor_id=admin_id)
        target = "MISSION_READY" if i < 18 else ("MEDICAL_SCHEDULED" if i == 18 else "TRAINING_COMPLETED")
        current = person.current_readiness.value if hasattr(person.current_readiness, "value") else str(person.current_readiness)
        if current != target:
            start = READINESS_WALK.index(current) + 1 if current in READINESS_WALK else 0
            for state in READINESS_WALK[start:]:
                from app.models.personnel import ReadinessState

                person = personnel_service.transition_readiness(db, person, ReadinessState(state), actor_id=admin_id, reason="demo seed")
                if state == target:
                    break
        ids.append(person.id)
    return ids


def _walk_cargo_forward(db: Session, admin_id: str, ship, pkg=None):
    """Walk a shipment (and optionally one package) forward to IN_TRANSIT."""
    order = NORMAL_FLOW
    cur = ship.status.value if hasattr(ship.status, "value") else str(ship.status)
    idx = order.index(cur) if cur in order else 0
    for state in order[idx + 1:8]:
        cargo_service.transition_shipment(db, ship, CargoStatus(state), actor_id=admin_id, location="Southern Ocean")
    if pkg is not None:
        cur = pkg.status.value if hasattr(pkg.status, "value") else str(pkg.status)
        idx = order.index(cur) if cur in order else 0
        for state in order[idx + 1:8]:
            pkg, _ = cargo_service.transition_package(db, pkg, CargoStatus(state), actor_id=admin_id, location="Southern Ocean")
    return pkg


def seed_cargo(db: Session, admin_id: str):
    from app.models.cargo import Container, DocType, Document, Package, Shipment

    ships = db.query(Shipment).filter(Shipment.expedition_id == EXP_ID).order_by(Shipment.created_at).all()
    # drop empty duplicates from interrupted runs (no containers/packages/docs)
    for extra in ships[3:]:
        if not db.query(Container).filter(Container.shipment_id == extra.id).count() and not db.query(Package).filter(Package.shipment_id == extra.id).count() and not db.query(Document).filter(Document.shipment_id == extra.id).count():
            db.delete(extra)
    db.commit()
    ships = db.query(Shipment).filter(Shipment.expedition_id == EXP_ID).order_by(Shipment.created_at).all()
    while len(ships) < 3:
        ships.append(cargo_service.create_shipment(db, EXP_ID, "Goa", "Bharati", actor_id=admin_id))
    ships = ships[:3]
    for s, ship in enumerate(ships):
        for c in range(5):
            code = f"DEMO-S{s + 1}C{c + 1}"
            if not db.query(Container).filter(Container.code == code).first():
                cargo_service.create_container(db, ship, code=code, actor_id=admin_id)
        have_docs = {d.doc_type.value if hasattr(d.doc_type, "value") else str(d.doc_type) for d in db.query(Document).filter(Document.shipment_id == ship.id).all()}
        for dt in (DocType.CARGO_DECLARATION, DocType.PACKING_LIST):
            if dt.value not in have_docs:
                cargo_service.generate_document(db, ship, dt, actor_id=admin_id)
        # refresh + walk forward (docs above unblock VERIFIED -> PACKED)
        ship = db.query(Shipment).filter(Shipment.id == ship.id).one()
        _walk_cargo_forward(db, admin_id, ship)
    # finish any half-walked packages, then top up to 100 across containers
    for pkg in db.query(Package).all():
        cur = pkg.status.value if hasattr(pkg.status, "value") else str(pkg.status)
        if cur in NORMAL_FLOW and NORMAL_FLOW.index(cur) < NORMAL_FLOW.index("IN_TRANSIT"):
            ship = db.query(Shipment).filter(Shipment.id == pkg.shipment_id).one()
            _walk_cargo_forward(db, admin_id, ship, pkg)
    containers = db.query(Container).all()
    cats = CATEGORIES
    n = db.query(Package).count()
    ci = 0
    while n < 100:
        container = containers[ci % len(containers)]
        ci += 1
        ship = db.query(Shipment).filter(Shipment.id == container.shipment_id).one()
        pkg = cargo_service.create_package(db, container, ship, f"demo kit {n + 1}", 20.0 + (n % 30), actor_id=admin_id)
        for k in range(2):
            cargo_service.add_item(db, pkg, f"demo item {n + 1}-{k + 1}", 2, "pcs", cats[(n + k) % len(cats)], actor_id=admin_id)
        _walk_cargo_forward(db, admin_id, ship, pkg)
        n += 1
        if n % 10 == 0:
            print(f"seed: {n}/100 packages", flush=True)


def seed_inventory(db: Session, admin_id: str):
    from app.models.inventory import InventoryItem

    if db.query(InventoryItem).count() >= 50:
        return
    for cat, items in STOCK:
        for name, qty, unit, minimum in items:
            if db.query(InventoryItem).filter(InventoryItem.name == name).first():
                continue
            item = inventory_service.create_item(db, actor_id=admin_id, name=name, category=cat, unit=unit, location="Bharati", minimum_stock=float(minimum))
            inventory_service.apply_transaction(db, item.id, "RECEIVE", float(qty), actor_id=admin_id, note="demo seed opening stock")


def seed_assets(db: Session, admin_id: str):
    have_assets = db.query(Asset).count()
    if have_assets < 20:
        for i, name in enumerate(ASSETS):
            sn = f"DEMO-A{i + 1:03d}"
            asset = db.query(Asset).filter(Asset.serial_number == sn).first()
            if not asset:
                asset = asset_service.create_asset(db, AssetCreate(name=name, serial_number=sn, location="Bharati", owner="NCPOR"), actor_id=admin_id)
            from app.models.asset import AssetStatus

            for state in ("RECEIVED", "COMMISSIONED", "IN_SERVICE"):
                current = asset.status.value if hasattr(asset.status, "value") else str(asset.status)
                if current == "IN_SERVICE":
                    break
                try:
                    asset = asset_service.transition_asset(db, asset, AssetStatus(state), actor_id=admin_id, reason="demo seed")
                except Exception:
                    break
    from app.models.asset import Vehicle

    have_veh = db.query(Vehicle).count()
    if have_veh < 10:
        idx = have_veh
        for vtype, count in VEHICLES:
            for _ in range(count):
                idx += 1
                if idx > 10:
                    break
                sn = f"DEMO-V{idx:03d}"
                if db.query(Asset).filter(Asset.serial_number == sn).first():
                    continue
                v = asset_service.create_vehicle(db, VehicleCreate(name=f"{vtype} {idx}", serial_number=sn, location="Bharati", registration_number=f"ANT-{100 + idx}", vehicle_type=vtype), actor_id=admin_id)
                from app.models.asset import AssetStatus

                asset = db.query(Asset).filter(Asset.id == v.asset_id).one()
                for state in ("RECEIVED", "COMMISSIONED", "IN_SERVICE"):
                    try:
                        asset = asset_service.transition_asset(db, asset, AssetStatus(state), actor_id=admin_id, reason="demo seed")
                    except Exception:
                        break


def _mission_members(db: Session, mid: str, pids: list[str]):
    for pid in pids:
        if not db.query(FieldMissionMember).filter(FieldMissionMember.mission_id == mid, FieldMissionMember.personnel_id == pid).first():
            db.add(FieldMissionMember(mission_id=mid, personnel_id=pid, role="MEMBER"))
    db.commit()


def seed_missions(db: Session, admin_id: str, personnel_ids: list[str]):
    from app.models.asset import Asset, Vehicle
    from app.models.mission import MissionStatus

    if db.query(FieldMission).count() >= 10:
        return
    vehicles = [v.id for v in db.query(Vehicle).limit(10).all()]
    equipment = [a.id for a in db.query(Asset).limit(10).all()]
    objectives = ["ice-core sampling", "crevasse survey", "met mast service", "penguin census", "fuel depot run", "ike traverse", "rock sampling", "antenna repair", "snow pit study", "rescue drill"]
    for i in range(10):
        mid = f"FM-DEMO-{i + 1:02d}"
        if db.query(FieldMission).filter(FieldMission.id == mid).first():
            continue
        team = [personnel_ids[(i * 2) % 18], personnel_ids[(i * 2 + 1) % 18]]
        m = mission_service.create_mission(
            db, MissionCreate(id=mid, expedition_id=EXP_ID, objective=objectives[i], leader_id=team[0], vehicle_id=vehicles[i % len(vehicles)] if vehicles else None, equipment_ids=equipment[:2], emergency_kit=True, emergency_plan="sat phone + shelter"), actor_id=admin_id,
        )
        _mission_members(db, mid, team)
        for state in ("PLANNED", "APPROVED"):
            mission_service.transition_mission(db, m, MissionStatus(state), actor_id=admin_id, actor_role="ADMIN")
        if i < 2:  # currently DEPLOYED
            mission_service.transition_mission(db, m, MissionStatus.DEPLOYED, actor_id=admin_id, actor_role="ADMIN")
        elif i < 4:  # pre-built CLOSED with reports
            mission_service.transition_mission(db, m, MissionStatus.DEPLOYED, actor_id=admin_id, actor_role="ADMIN")
            mission_service.transition_mission(db, m, MissionStatus.ACTIVE, actor_id=admin_id, actor_role="ADMIN")
            checkin_service.submit_check_in(db, mid, actor_id=admin_id, note="departed", location="Bharati")
            checkin_service.submit_check_in(db, mid, actor_id=admin_id, note="task done, returning", location="WP-2")
            checkin_service.post_comms(db, mid, author="demo", message="drilling complete, heading home")
            mission_service.transition_mission(db, m, MissionStatus.RETURNED, actor_id=admin_id, actor_role="ADMIN")
            from app.models.report import MissionOutcome

            closeout_service.close_mission(db, mid, actor_id=admin_id, closing_summary=f"demo closeout for {objectives[i]}", outcome=MissionOutcome.SUCCESS, vehicle_condition="RETURNED", equipment={a: "RETURNED" for a in equipment[:2]})


def seed_incidents(db: Session, admin_id: str):
    from app.models.incident import Incident, IncidentStatus, IncidentType
    from app.models.mission import FieldMission
    from app.models.personnel import Personnel

    if db.query(Incident).count() >= 20:
        return
    missions = [m.id for m in db.query(FieldMission).limit(10).all()]
    people = [p.id for p in db.query(Personnel).limit(10).all()]
    n = db.query(Incident).count()
    for i in range(n, 20):
        inc = incident_service.create_incident(
            db, IncidentCreate(incident_type=IncidentType(INCIDENT_TYPES[i % len(INCIDENT_TYPES)]), personnel_id=people[i % len(people)] if people else None, mission_id=missions[i % len(missions)] if missions else None, last_location=f"WP-{i % 5}", detail=f"demo historical incident {i + 1}"), actor_id=admin_id,
        )
        for state in ("ASSESSING", "RESPONDING", "RESOLVED", "CLOSED"):
            incident_service.transition_incident(db, inc, IncidentStatus(state), actor_id=admin_id, reason="demo history")


def seed_route(db: Session):
    if db.query(RouteLeg).count() >= 4:
        return
    legs = [
        (0, "Goa", "Mumbai", "RAIL", "120 TEU", "ARRIVED"),
        (1, "Mumbai", "Cape Town", "SHIP", "400 TEU", "EN_ROUTE"),
        (2, "Cape Town", "Antarctica", "ICEBREAKER", "200 TEU", "SCHEDULED"),
        (3, "Antarctica", "Bharati", "TRAVERSE", "60 TEU", "SCHEDULED"),
    ]
    for seq, origin, dest, mode, cap, status in legs:
        db.add(RouteLeg(expedition_id=EXP_ID, seq=seq, origin=origin, destination=dest, mode=mode, capacity=cap, status=LegStatus(status)))
    db.commit()


def run(db: Session) -> dict:
    admin_id = seed_users(db)
    seed_stations(db)
    seed_expedition(db, admin_id)
    pids = seed_personnel(db, admin_id)
    seed_cargo(db, admin_id)
    seed_inventory(db, admin_id)
    seed_assets(db, admin_id)
    seed_missions(db, admin_id, pids)
    seed_incidents(db, admin_id)
    seed_route(db)
    from app.models.asset import Asset, Vehicle
    from app.models.cargo import Package, Shipment
    from app.models.incident import Incident
    from app.models.inventory import InventoryItem
    from app.models.mission import FieldMission
    from app.models.personnel import Personnel

    return {
        "users": db.query(User).count(),
        "personnel": db.query(Personnel).count(),
        "shipments": db.query(Shipment).filter(Shipment.expedition_id == EXP_ID).count(),
        "packages": db.query(Package).count(),
        "inventory": db.query(InventoryItem).count(),
        "assets": db.query(Asset).count(),
        "vehicles": db.query(Vehicle).count(),
        "missions": db.query(FieldMission).count(),
        "incidents": db.query(Incident).count(),
        "open_incidents": db.query(Incident).filter(~Incident.status.in_(["RESOLVED", "CLOSED"])).count(),
        "route_legs": db.query(RouteLeg).count(),
    }


if __name__ == "__main__":
    import time

    from sqlalchemy.exc import OperationalError

    from app.database import SessionLocal

    last_err = None
    for attempt in range(1, 4):
        db = SessionLocal()
        try:
            print(run(db))
            break
        except OperationalError as exc:
            last_err = exc
            print(f"attempt {attempt}: connection dropped, retrying in 5s...")
            time.sleep(5)
        finally:
            db.close()
    else:
        raise last_err
