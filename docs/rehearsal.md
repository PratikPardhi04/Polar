# POLARIS demo rehearsal — EXP-46ISEA-2026 → Bharati (≈10 min)

Seed first: `python database/seed/seed_demo.py` (logins use `polaris123`).
Login as `admin@bharati.in`. Keep the Audit tab open — every step below lands there.

1. **Mission created** — dashboard header shows EXP-46ISEA-2026 → Bharati.
2. **Personnel** — 20 seeded (18 MISSION_READY / 1 MEDICAL_SCHEDULED / 1 TRAINING_COMPLETED).
3. **Cargo** — 100 BX packages IN_TRANSIT with QR + compliance docs per shipment.
   Scan one: `POST /api/v1/scan {"package_id": "BX-…", "to_status": "RECEIVED_AT_STATION"}`.
4. **Logistics problem** — Simulation panel → Cargo Delay. Ask POLARIS
   "Which cargo can affect tomorrow's Bharati mission?" → draft appears, bell rings.
5. **Field mission** — FM-DEMO-01 (ice-core), team/vehicle assigned, live Bharati
   weather card, Go/No-Go green, DEPLOYED.
6. **Offline mode** — Flutter app airplane toggle → scan → "SYNC: PENDING" →
   toggle off → Sync now → ACKNOWLEDGED (queue badge clears).
7. **Emergency** — Simulate Missed Check-in (grace → escalation → draft
   MISSING_PERSON, no SOS) → Trigger SOS → red SOS badge + simulated SMS/email
   in bell, WS push refreshes the incident panel live.
8. **Command Centre** — incident detail shows person/mission/location/team/
   vehicle/weather/comms. Audit tab → search the package/person id for the full trail.
9. **AI** — "What resources can respond to this incident?" → recommendations +
   explicit APPROVE (audited, nothing auto-executes).
10. **Closeout** — close FM-DEMO-03 (pre-built RETURNED demo mission) → open the
    Mission Report PDF. Situation Reports tab → generate + Publish as Station Leader.

Reset between runs: re-seed is idempotent for counts; for a clean slate, drop
`polaris_demo.db` (SQLite) or reset the Postgres database, migrate, re-seed.
