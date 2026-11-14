# Pramaan Android app (Capacitor 7)

The same web app in a thin native shell, installed by sending the APK file to a phone. No Play Store listing is needed or planned. The shell loads your deployed site over
https (so one deploy updates the website, the installed web app and this app), stays inside its own origin, shows an offline page with no connection, and gives the
page native touches (haptic confirmation when a certificate is issued, the Android back button, a status bar that matches the page).

The phone cannot reach a server on your laptop unless they share a network, so **the website and API must be hosted somewhere once** (see `docs/deploy`). After that the
phone works with the laptop switched off.

## Build an APK (works on this machine: JDK 21 and the Android SDK are installed)
1. `pnpm install --ignore-workspace` (once)
2. `pnpm set-url https://your-domain.example` (your deployed site). For a quick test on your own Wi-Fi only: `pnpm set-url http://192.168.1.20:3000 --dev`.
3. `pnpm build:debug` then take `android/app/build/outputs/apk/debug/app-debug.apk` to the phone (USB, WhatsApp to yourself, Drive) and open it. Android asks once to allow
   installs from that source.
4. A debug APK is signed with a throwaway key: fine for your own phones and testers, and a later build installs over it only if it was built on the same machine. A release
   build for wider sharing needs your own signing key (`keytool`), which you keep private and never commit.

## What is here
- `capacitor.config.json`: the site URL, no cleartext (unless `--dev`), no mixed content, web debugging off, status bar and splash in the brand colours.
- `www/`: the offline page the app shows with no connection.
- `scripts/test-config.mjs`: `pnpm test` guards those safety settings.
- `scripts/set-url.mjs`: points the app at your site.

## Not done (needs your accounts)
- Push notifications: the plugin is installed, but the server side is not built (it needs a device-token table, a migration, and a sender) and it needs a Firebase
  `google-services.json`. Until then nothing is sent.
- Not run on a device or emulator: this machine has no emulator image. The APK builds; open it on a real phone and report anything odd.
