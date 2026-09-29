# Deploying POLARIS on Vercel

Two Vercel projects (frontend static + backend serverless). The AI service is
optional — the dashboard degrades gracefully when it is unreachable.

## 0. What changes on serverless (read this first)

| Concern | Local | Vercel |
|---|---|---|
| Database | SQLite file / local Postgres | External Postgres required (Neon, Supabase, or Vercel Postgres). Serverless disks are ephemeral — SQLite data would vanish. |
| Check-in escalation worker | APScheduler in-process tick | Disabled when `VERCEL=1` (auto-set). Use Vercel Cron → `POST /api/v1/check-ins/advance-cron?cron_secret=…` every minute instead. |
| WebSocket alerts (`/ws/alerts`) | Live push | **Not supported** on serverless functions. The incident panel already falls back to polling (`○ live push offline`). |
| Generated PDFs | Persist in `generated_docs/` / `generated_reports/` | Ephemeral — regenerated on demand per request, which is all the demo needs. |
| Function timeout | None | 10 s default (Hobby). Cold starts with reportlab/qrcode imports can approach this — keep the demo warm by clicking through once before presenting. |

## 1. Database (do once)

1. Create a free Postgres at [Neon](https://neon.tech) or Supabase. Use the
   **pooled** connection string if offered.
2. From your laptop, point at it and migrate + seed:
```powershell
$env:DATABASE_URL="postgresql+psycopg2://USER:PASS@HOST:5432/polaris"
alembic -c database/alembic.ini upgrade head
python database/seed/seed_demo.py   # demo logins use polaris123
```

## 2. Backend project

1. Vercel → Add New Project → import this repo. Set **Root Directory** to `backend/`.
2. Environment Variables:
   - `DATABASE_URL` — same pooled Postgres URL (use `postgresql+psycopg2://…`)
   - `JWT_SECRET_KEY` — fresh random string (`python -c "import secrets; print(secrets.token_hex(32))"`)
   - `CORS_ORIGINS` — `https://<your-frontend>.vercel.app`
   - `CRON_SECRET` — fresh random string (also used below)
3. Deploy. `backend/api/index.py` exports the FastAPI app — no adapter needed.
   Note the URL, e.g. `https://polaris-api.vercel.app`.

## 3. Check-in cron (recommended)

Vercel Dashboard → your backend project → Settings → Cron Jobs → Add:
- Path: `/api/v1/check-ins/advance-cron?cron_secret=<CRON_SECRET>`
- Schedule: `* * * * *`

Without this, missed-check-in escalation only advances when someone hits the
manual trigger (`POST /api/v1/check-ins/advance`, ops roles).

## 4. Frontend project

1. Add New Project → same repo. **Root Directory** = `frontend/`, Framework Preset = Vite (auto-detected; no rewrites needed — the app uses hash routing).
2. Environment Variables (baked in at build time — redeploy after changing):
   - `VITE_API_URL` = `https://polaris-api.vercel.app`
   - `VITE_AI_URL` = your AI URL, or leave default (Ask POLARIS shows a clear error when unreachable)
3. Deploy. Open the URL → landing page → login with a seeded account.

## 5. Smoke test (production)

1. Login works, dashboard cards populate.
2. Simulation panel (ADMIN): Trigger SOS → incident appears, bell rings.
3. Audit → events tab shows the trail; Export CSV downloads.
4. Ask POLARIS → if the AI service isn't deployed, you get the "is it running?" message instead of a hang.

## 6. Optional: AI service as a third project

Same recipe as §2 with Root Directory `ai/` (`ai/main.py` is the app, but
Vercel needs it under `api/` — copy or move `main.py`+`tools.py`+`agents.py`
into `ai/api/` with an `index.py` re-export, mirroring `backend/api/index.py`).
Set `BACKEND_URL` to the backend URL and `CORS_ORIGINS` to the frontend URL.
