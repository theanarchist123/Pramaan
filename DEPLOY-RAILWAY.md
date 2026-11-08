# Deploying Pramaan: Vercel + Railway + Supabase

**Vercel** (web) + **Railway** (API) + **Supabase** (Postgres with pgvector).
Railway is not free: there is a one-time trial credit, then a monthly plan plus usage. The always-on API (Chromium for PDFs + embeddings) is the main cost — check Railway's current pricing.

> These steps were written from the repo's needs, not tested on a live Railway project. If a screen differs, follow the intent.

## 0. Before you start
- Push the repo to GitHub (never commit `.env`; it's git-ignored).
- Generate two secrets locally:
  ```powershell
  # JWT secret
  [Convert]::ToBase64String((1..48 | % { Get-Random -Max 256 }) -as [byte[]])
  # Ed25519 signing seed (keep it safe: it signs every certificate; losing it breaks verification of old ones)
  [Convert]::ToBase64String((1..32 | % { Get-Random -Max 256 }) -as [byte[]])
  ```

## 1. Database — Supabase
1. supabase.com → New project (choose a region near your Railway region, e.g. Mumbai/Singapore). Save the database password.
2. **Connect** → **Session pooler** → copy the URI (it ends in `:5432/postgres`). Use the **Session pooler**, not "Direct" (IPv6 only, Railway can't reach it) and not the "Transaction pooler" on port 6543 (breaks asyncpg's prepared statements).
3. Replace `[YOUR-PASSWORD]` in it. If the password has special characters (`@ : / #`), URL-encode them (`@` → `%40`).
4. Add `?sslmode=require` at the end if it isn't there — the app converts it for asyncpg.
5. The API runs `CREATE EXTENSION IF NOT EXISTS vector` and creates its own tables on first start; nothing to set up by hand.

Free-tier limits to know: 500 MB database, and **free projects are paused after about a week of inactivity** (the whole app would then fail until you resume it). Anyone who uses the site regularly keeps it awake; for a submission, open the dashboard before judging or upgrade the project.

## 2. Backend service — Railway
New → GitHub repo → **Root Directory: `backend`** (it builds `backend/Dockerfile`).

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Supabase **session pooler** URI from step 1 |
| `PUBLIC_BASE_URL` | the **Vercel production URL** (also drives CORS and QR links) — e.g. `https://pramaan.vercel.app` |
| `API_BASE_URL` | this service's public URL |
| `RENDER_BASE_URL` | same as `PUBLIC_BASE_URL` |
| `JWT_SECRET` | the first secret above |
| `SIGNING_KEY_B64` | the second secret above |
| `LLM_MODE` / `LLM_PROVIDER` | `live` / `gemini` |
| `GEMINI_API_KEY` | your key |
| `WIKIMEDIA_CONTACT` | an email or URL |
| `PLUGINS_ENABLED` / `WEBHOOK_ALLOW_PRIVATE` | `false` / `false` |
| `RAILWAY_RUN_UID` | `0` (needed to write to the mounted volume) |

Then: **Settings → Networking → Generate domain**, and **Add a Volume** mounted at `/srv/backend/data` (uploads, rendered certificates). Give the service at least 2 GB of memory (Chromium + embeddings model). Health check path: `/healthz`.

CORS allows exactly one web origin (`PUBLIC_BASE_URL`), so use your stable production domain, not Vercel's per-deploy preview URLs.

## 3. Web — Vercel
Import the repo → **Root Directory: `apps/web`** → framework Next.js (auto-detected).

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | the Railway backend's public URL — baked in at build time, so set it *before* deploying and redeploy if it changes |

Deploy, then put the final Vercel URL into the backend's `PUBLIC_BASE_URL` and `RENDER_BASE_URL` and let Railway redeploy.

## 4. Seed + first admin
Demo data is optional. To load it once, from your machine:
```powershell
cd backend
$env:DATABASE_URL = "<Supabase session pooler URI>"
.venv\Scripts\python scripts\seed_demo.py
```
This also creates `admin@pramaan.demo / pramaan-demo-1` — **change that password** (or delete the account) on anything public.
For real use, register normally and promote your own account to admin in the database.

## 5. Check it
- `https://<api>/healthz` → `{"status":"ok", ...}`
- `https://<api>/docs` → API docs
- `https://<web>` → onboard, issue a certificate, download the PDF, scan the QR.

## 6. Point the apps at it
- Desktop app: edit `config.json` next to `Pramaan.exe` → `{ "url": "https://<web>" }`.
- Developers page examples use the API URL you built the web app with.

## Things to know
- **Shilpkar (AI-written plugins)** needs Docker for its sandbox, which Railway doesn't give you. It stays disabled in the deployed app; use it locally.
- **Gemini free-tier quotas** limit AI throughput under heavy use, whatever you host on.
- **Back up Postgres** (Supabase backups on paid plans, or `pg_dump` on a schedule). The certificate transparency log lives there.
