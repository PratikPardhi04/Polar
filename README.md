# POLARIS — Integrated Polar Expedition Logistics (SIH 2026, PS 26062)
Demo identity: EXP-46ISEA-2026 → Bharati station.

## Run locally
```powershell
Copy-Item .env.example .env
docker compose up --build   # needs Docker Desktop running
# backend: http://localhost:8000/docs  |  /health
# ai: http://localhost:8001/health
```
Migrations (run from repo root; `%(here)s` makes the ini path CWD-independent):
```powershell
$env:DATABASE_URL="postgresql+psycopg2://polaris:polaris@localhost:5432/polaris"
alembic -c database/alembic.ini upgrade head
python database/seed/seed_demo.py   # demo logins use password polaris123
```
No-Docker fallback (SQLite — fine for rehearsal; no geo columns are used):
```powershell
$env:DATABASE_URL="sqlite:///./polaris_demo.db"
alembic -c database/alembic.ini upgrade head
python database/seed/seed_demo.py
python -m uvicorn app.main:app --app-dir backend --reload
```

## Deploying (Vercel)
See [docs/deployment.md](docs/deployment.md): backend as a serverless project
(`backend/` root, external Postgres required), frontend as a static project,
Vercel Cron replacing the in-process scheduler. Known serverless limits
(no WebSocket push, ephemeral PDFs, 10 s default timeout) are documented there.
