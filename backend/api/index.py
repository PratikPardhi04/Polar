"""Vercel serverless entrypoint.

Deploy the `backend/` directory as its own Vercel project (Root Directory =
`backend`). Vercel serves every file under `api/` as a serverless function and
natively handles the exported ASGI app — no adapter needed.

Required env vars (Vercel dashboard → Settings → Environment Variables):
  DATABASE_URL  — external Postgres (Neon/Supabase/Vercel Postgres), e.g.
                  postgresql+psycopg2://user:pass@host:5432/polaris
  JWT_SECRET_KEY — long random string (generate a fresh one, NOT the repo default)
  CORS_ORIGINS  — your frontend URL, e.g. https://polaris-app.vercel.app
  CRON_SECRET   — random string authorizing POST /check-ins/advance-cron

Migrations + seed run from your own machine against the same DATABASE_URL
(see docs/deployment.md) — serverless builders can't see database/.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402,F401  (Vercel serves this ASGI app)
