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
- **Staff console:** see the next section.
- **AI-written plugin sandbox** needs Docker, which Render's web services do not give you; it stays off (`PLUGINS_ENABLED=false`).
- Supabase free projects pause after about a week of inactivity.

## Staff console (apps/admin) on Vercel, no domain needed
**The catch.** Staff sign in with a cookie (`__Host-pramaan_admin`, SameSite=Strict). A browser sends a Strict cookie only when the page and the API are on the same site. `*.vercel.app` and `*.onrender.com` are different sites, so a console that called the API directly could open but never stay signed in. The fix needs no domain: the console forwards its API calls through **its own address** (a small forwarding route, `apps/admin/src/app/api/[...path]/route.ts`), so the browser only ever talks to one site. Only the paths the console uses are forwarded (`/v1/admin/*`, `/v1/auth/mfa/*`, `/v1/search`, `/v1/images/sector/*`); `scripts/test-proxy.mjs` guards that list. If `API_INTERNAL_URL` is missing, the login page says so in words (HTTP 503) instead of a blank 404.

1. **Vercel -> Add New Project** -> same repo -> **Root Directory `apps/admin`**. Keep "Include source files outside of the Root Directory" ON (the console uses `packages/ui`). Framework: Next.js.
2. Environment variables for that project (then deploy):
   - `NEXT_PUBLIC_API_URL` = `/staff/api` (a path on the console itself, not the Render address)
   - `API_INTERNAL_URL` = your Render URL, e.g. `https://pramaan-api-u4ag.onrender.com` (no trailing slash)
   Vercel applies a changed variable only to the NEXT deployment, so after adding or changing one, redeploy (Deployments -> the latest -> Redeploy).
3. Note the console's Vercel address, e.g. `https://pramaan-staff.vercel.app`. The console lives at `https://pramaan-staff.vercel.app/staff`.
4. **Render (API)**: set `ADMIN_BASE_URL` = that console address (just the origin, `https://pramaan-staff.vercel.app`) and let it redeploy. The API only accepts staff state-changing requests whose Origin matches it. Leave `PUBLIC_BASE_URL` as your member site.
5. **First staff account.** Register normally on the member site, then in Supabase -> SQL editor: `update users set role = 'admin' where email = 'you@example.com';`. Open `https://pramaan-staff.vercel.app/staff/login`, sign in, and set up the authenticator (see below). Change or delete the demo admin (`admin@pramaan.demo`) now.
6. **Member site link.** In the MEMBER site's Vercel project add `NEXT_PUBLIC_STAFF_URL` = `https://<your-staff-site>.vercel.app/staff` and redeploy, so the "Staff console" item in an admin's account menu opens the staff site. The bare staff address (`https://<your-staff-site>.vercel.app/`) also goes straight to the sign-in screen.
7. **Demo admin.** `admin@pramaan.demo` has a public password. After your own account is admin, run in Supabase SQL: `update users set role = 'person' where email = 'admin@pramaan.demo';`
8. **Check:** wrong password shows an error; after a good sign-in the Review page loads and stays signed in after a refresh; `/staff/security` shows the QR code; sign out works.

**Authenticator.** Any authenticator app works (Google Authenticator, Microsoft Authenticator, Authy, 1Password, Aegis). You do not sign in to Google or anyone else: the app just stores a key and shows 6 digits. Scan the QR code on the Security page, or type the key by hand. Save the recovery codes it shows once.

**Not tried on a live host.** The proxy is covered by a config test, not yet by a real Vercel + Render run. If the Vercel build or the sign-in fails, send the build log or the exact error. A custom domain (console, API and site under one registrable domain) also works and avoids the proxy; then set `NEXT_PUBLIC_API_URL` to the API address and `COOKIE_SAMESITE=lax`.
