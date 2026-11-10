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
5. **Migrations (Alembic).** The backend image runs `alembic upgrade head` before starting, which enables `vector`, creates/updates the tables and the read-only views plugins use. The API refuses to start on a database that was never migrated. An existing database built by the old `create_all` is picked up safely (the baseline only creates what is missing). For any future schema change write a revision (`cd backend && alembic revision -m "what changed"`) and deploy; never edit tables by hand.

Free-tier limits to know: 500 MB database, and **free projects are paused after about a week of inactivity** (the whole app would then fail until you resume it). Anyone who uses the site regularly keeps it awake; for a submission, open the dashboard before judging or upgrade the project.

## 2. Backend service — Railway
New → GitHub repo → **Root Directory: `backend`** (it builds `backend/Dockerfile`).

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Supabase **session pooler** URI from step 1 |
| `PUBLIC_BASE_URL` | the **Vercel production URL** (also drives CORS and QR links) — e.g. `https://pramaan.vercel.app` |
| `API_BASE_URL` | this service's public URL |
| `RENDER_BASE_URL` | same as `PUBLIC_BASE_URL` |
| `JWT_SECRET` | the first secret above (`python backend/scripts/gen_secrets.py` prints both) |
| `SIGNING_KEY_B64` | the second secret above. **Required**: the API refuses to start without it outside localhost, so a lost volume can never silently create a new key |
| `SIGNING_RETIRED_PUBLIC_KEYS` | empty now. When you rotate the signing key, put the OLD public key(s) here (comma-separated) so old certificates keep verifying; `/.well-known/pramaan-keys.json` lists them all |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `SMTP_FROM` | needed in production: applicants confirm their email with a one-time code before verification |
| `WORKER_INLINE` | `true` (default) runs webhook retries and scheduled email inside the API. Set `false` if you run a separate worker (below) |
| `LLM_MODE` / `LLM_PROVIDER` | `live` / `gemini` |
| `GEMINI_API_KEY` | your key |
| `WIKIMEDIA_CONTACT` | an email or URL |
| `PLUGINS_ENABLED` / `WEBHOOK_ALLOW_PRIVATE` | `false` / `false` |
| `RAILWAY_RUN_UID` | `0` (needed to write to the mounted volume) |

Then: **Settings → Networking → Generate domain**, and **Add a Volume** mounted at `/srv/backend/data` (uploads, rendered certificates). Health check path: `/healthz`.

### Staying on Railway's free tier (about 512 MB RAM, 0.5 GB volume)
The volume is only disk (uploads + cached PDFs): 0.5 GB is plenty. **RAM is the limit**, and the semantic-search model alone needs about 700 MB. So use the lite configuration:

| Setting | Value | Why |
|---|---|---|
| Build variable `WITH_EMBEDDINGS` | `false` | leaves the ML model out of the image (Railway passes service variables to Docker as build args) |
| `EMBEDDINGS` | `hash` | search uses the lexical fallback instead of the model |

Measured locally in a container hard-limited to 512 MB: idle about 100 MB; a certificate PDF render peaks at about 320 MB; three simultaneous cold renders also peaked at about 320 MB with no out-of-memory kills (renders run one at a time). It fits, with modest headroom. This was measured on a local Docker, not on Railway itself.

Cost of this setup: search matches words (names, places, sectors) rather than meaning, so "clean-energy innovators" is found by those words but not by synonyms. If you later get 1 GB or more of RAM, remove both settings to turn the multilingual model back on.

CORS allows exactly one web origin (`PUBLIC_BASE_URL`; localhost origins are allowed only when that URL is itself localhost), so use your stable production domain, not Vercel's per-deploy preview URLs.

### Sign-in cookie
The browser session is an `httpOnly` cookie set by the API (`SameSite=None; Secure` in production because the web app and API are on different domains). State-changing requests that arrive with the cookie must carry an `Origin` equal to `PUBLIC_BASE_URL`, which blocks cross-site forgery. **Safari and some privacy settings block third-party cookies**, which breaks sign-in when the web app and API are on unrelated domains (`*.vercel.app` + `*.up.railway.app`). The robust fix is one registrable domain for both, e.g. `app.example.com` (Vercel) and `api.example.com` (Railway); then set `COOKIE_SAMESITE=lax`. API clients and SDKs keep using `Authorization: Bearer` / `X-API-Key`; logging out revokes every token issued before it.

### Background worker and the AI-code sandbox
Webhook deliveries and scheduled emails go through database tables claimed with `FOR UPDATE SKIP LOCKED`, so restarts lose nothing and several replicas never send the same one twice. By default the API runs that loop itself. For production, run it as its own Railway service (same image, start command `python -m app.worker`) and set `WORKER_INLINE=false` on the API.

AI-written plugin checks run inside Docker, which the API image does not have and should not. Outside localhost they are **queued** (status `queued`) until `python -m app.worker` runs on a machine with Docker and the `pramaan-sandbox` image (`docker build -t pramaan-sandbox sandbox/`) and the same `DATABASE_URL`. `SANDBOX_MODE=worker|inline|auto` overrides this. Until such a worker exists, queued changes simply wait; nothing runs unchecked.

### Safety switches
`REQUIRE_EMAIL_VERIFICATION`, `HUMAN_APPROVAL_FIRST_LISTING` and `AWARD_CLAIMS_NEED_HUMAN` default to `true`: a person's first public listing, and any award claim, is approved by an admin in the review queue even when every check passes. Edits to an approved profile's public text send it back to review.

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
- `https://<api>/healthz` → `{"status":"ok"}` (nothing else is revealed on purpose)
- `https://<api>/docs` → API docs
- `https://<web>` → onboard, issue a certificate, download the PDF, scan the QR.

## 6. Point the apps at it
- Desktop app: edit `config.json` next to `Pramaan.exe` → `{ "url": "https://<web>" }`.
- Developers page examples use the API URL you built the web app with.

## Things to know
- **Shilpkar (AI-written plugins)** needs Docker for its sandbox, which Railway doesn't give you. It stays disabled in the deployed app; use it locally.
- **Gemini free-tier quotas** limit AI throughput under heavy use, whatever you host on.
- **Back up Postgres** (Supabase backups on paid plans, or `pg_dump` on a schedule). The certificate transparency log lives there.
