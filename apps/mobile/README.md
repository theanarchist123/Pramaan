# Pramaan Android app (Capacitor)

The web app in a thin native shell. It loads the live site over https (so one deploy updates web and app), stays inside its own origin, ships an offline page, and registers for push.

## What is here
- `capacitor.config.json`: the site URL (`server.url`: **set it to your real domain**, and the same host in `allowNavigation`), no cleartext, no mixed content, web debugging off.
- `www/`: the offline page the app shows with no connection.
- `scripts/test-config.mjs`: `pnpm test` guards those safety settings.

## What you do (needs your accounts and the Android SDK)
1. `pnpm install` then `npx cap add android`.
2. Firebase: create a project, add an Android app with id `in.pramaan.app`, put `google-services.json` in `android/app/`. Do not commit it if it is private to your org.
3. The server side of push is not built: it needs a device-token table (a migration) and a sender. Until then the app can register but nothing sends.
4. `pnpm sync`, `pnpm open`, build a signed release in Android Studio. Store listing text, screenshots and a privacy policy are yours to supply; the app collects nothing beyond what the website does.

## Not verified
Nothing here has been built on a device or emulator: this machine had no Android SDK set up for it. Treat it as a starting point and run it once before relying on it.
