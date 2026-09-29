"""Seed stations + EXP-46ISEA-2026. All rows tagged SYNTHETIC_DEMO where applicable."""
from app.database import SessionLocal
from app.models.expedition import DataSource, Expedition, ExpeditionStatus
from app.models.station import STATION_SEED, Station

EXP_ID = "EXP-46ISEA-2026"


def run():
    db = SessionLocal()
    try:
        for seed in STATION_SEED:
            if not db.query(Station).filter(Station.code == seed["code"]).first():
                db.add(Station(**seed))
        db.flush()
        bharati = db.query(Station).filter(Station.code == "BHARATI").one()
        if not db.query(Expedition).filter(Expedition.id == EXP_ID).first():
            db.add(
                Expedition(
                    id=EXP_ID,
                    name="46th Indian Scientific Expedition to Antarctica",
                    primary_station_id=bharati.id,
                    mission_type="Polar Environmental Monitoring",
                    status=ExpeditionStatus.PLANNED,
                    description="Demo expedition — Bharati station focus",
                    source=DataSource.SYNTHETIC_DEMO,
                )
            )
        db.commit()
        print(f"seeded {EXP_ID} at Bharati")
    finally:
        db.close()


if __name__ == "__main__":
    run()
