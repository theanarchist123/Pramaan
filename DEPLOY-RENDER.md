# Deploying the API on Render (web on Vercel, database on Supabase)

`render.yaml` in the repo root describes the API service. These steps are written from the repo and Render's docs; **not yet run on a live Render account**. If a screen differs, follow the intent.

## Why Render and not Vercel for the API
Vercel runs short serverless functions. This API needs a long-lived server: a headless browser to render certificate PDFs, live event streaming (SSE) during onboarding, a background loop (emails, webhooks, guest clean-up), an in-memory rate limiter and, optionally, an embedding model. Those do not fit Vercel's function size and time limits. Keep Vercel for the Next.js sites only.

## Free tier: what to expect (Render's own page: <https://render.com/docs/free>)
- A free web service **sleeps after 15 minutes without traffic** and takes about a minute to wake. The first visit after a quiet period is slow.
- **No persistent disk on free services**: files written to disk (member photo uploads, rendered PDFs) vanish on every restart or sleep. Certificates and profiles are safe (they live in Supabase), but **uploaded photos are not**. Fix: a paid instance with a disk, or move photo storage to Supabase Storage (not built).
- The 512 MB memory is tight with Chromium for PDFs. The Blueprint uses the lite search setting (`EMBEDDINGS=hash`).

## Steps
1. Push the repo to GitHub (never commit `.env`).
2. Generate two secrets on your machine and keep copies somewhere safe: `python backend/scripts/gen_secrets.py` (prints a JWT secret and a signing seed). The signing seed signs every certificate; if it is lost, old certificates stop verifying.
3. Render dashboard -> New -> **Blueprint** -> pick the repo. It reads `render.yaml`. Fill each prompted value there (never in chat or in the repo):
   - `DATABASE_URL`: Supabase **session pooler** URI (port 5432), password URL-encoded.
   - `PUBLIC_BASE_URL` and `RENDER_BASE_URL`: your Vercel production URL. `API_BASE_URL`: the Render URL (shown after the first deploy; add it, then redeploy).
   - `SIGNING_KEY_B64`, `GEMINI_API_KEY`, `WIKIMEDIA_CONTACT`, SMTP values.
4. The container runs `alembic upgrade head` on start, so the Supabase database is migrated by the first deploy. Check `https://<api>/healthz`.
5. **Vercel (web)**: set `NEXT_PUBLIC_API_URL` to the Render URL and redeploy (it is baked in at build time).
6. Cross-site sign-in: with `*.vercel.app` and `*.onrender.com` the session cookie is third-party; Safari and some privacy settings block it. The robust fix is one custom domain for both (e.g. `app.example.com` and `api.example.com`), then set `COOKIE_SAMESITE=lax`.
7. Android app: `cd apps/mobile`, `pnpm set-url https://<your-vercel-url>`, `pnpm build:debug`.

## Things this guide does not cover
- **Staff console (`/staff`)**: the web app forwards `/staff` to the separate admin app (`ADMIN_INTERNAL_URL`). That app needs its own Vercel project (Root Directory `apps/admin`) and the web project needs `ADMIN_INTERNAL_URL` pointing at it. Not tried in production.
- **AI-written plugin sandbox** needs Docker, which Render's web services do not give you; it stays off (`PLUGINS_ENABLED=false`).
- Supabase free projects pause after about a week of inactivity.
