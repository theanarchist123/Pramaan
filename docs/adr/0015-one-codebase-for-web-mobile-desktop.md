# ADR 0015: One codebase for web, phone and desktop

Status: **accepted 2026-11-14 (owner approved: no Play Store listing, one codebase, native feel where it matters).**

## Decision
- **Web:** Next.js (`apps/web`), the only place UI is written.
- **Phone (Android):** the same site as an installable web app (PWA: manifest, service worker, offline page, share target, shortcuts) **and** a Capacitor 7 shell
  (`apps/mobile`) that loads the deployed site. The APK is sent to phones directly; no store listing. iOS would reuse the same shell but needs a Mac and an Apple
  developer account, so it is not set up.
- **Desktop (Windows, macOS, Linux):** Electron shell (`apps/desktop`) around the same site, with offline certificate verification, deep links and a staff-console build.
- **Not chosen:** React Native / Flutter (every screen would be written again), native Kotlin/Swift (same, twice).

## Why a shell that loads the hosted site
Profiles, search, document checks and signing need a server, and the site uses server-rendered routes (`/p/[slug]`, `/verify/[code]`, share images), so it cannot be exported
as static files into the app. Loading the hosted site means one deploy updates every surface. The cost: the **website and API must be hosted** (Vercel/Railway/Supabase,
see `docs/deploy`); a phone cannot reach a laptop that is switched off. The only thing that works with no server is checking a certificate's signature against cached public keys,
which the desktop app already does (`apps/desktop/src/verify.js`); the phone does not yet.

## Native feel
Same design, native touches through `src/lib/native.ts` (no-ops in a browser): haptic confirmation on a server-confirmed certificate (I-9 still holds: it fires only after the
server says so), Android back button (Capacitor default: back in history, then exit), status bar and splash in the brand colours, safe-area padding (`viewport-fit=cover`),
camera/file capture through the normal file input, the system share sheet through the web share API. Navigation keeps the owner's chosen top tabs (a second row on phones).

## Safety settings (guarded by `apps/mobile/scripts/test-config.mjs`)
https only (plain http only via `set-url --dev`, never committed), no mixed content, navigation limited to the site's own host, web debugging off, no dependencies besides Capacitor.

## Not verified
- The APK was built on a Windows machine with JDK 21 and Android SDK 35; it has **not been run on a phone or emulator** (no emulator image installed).
- Capacitor 7 and Android requirements were taken from the installed packages and the generated project, not re-read from the official docs here. Check before a wider rollout.
- Push notifications: the plugin is installed; there is no server side (device-token table, migration, sender) and no Firebase file.
