# ADR 0006: desktop shell: stay on Electron for now, revisit Tauri

Status: accepted for now (2026-11-12). This is a desk decision, not the "spike" the plan (DSK-06) asks for: no Tauri build was made. The spike is still open.

## What was checked (official source: https://v2.tauri.app/reference/webview-versions/)
- Tauri uses the operating system's own web view: WebView2 (Chromium-based) on Windows, WKWebView on macOS, webkit2gtk on Linux.
- On macOS the web view updates only with the operating system, so unsupported macOS versions get no web-view updates. On Linux the version depends on the distribution.
- A third-party 2026 article (not an official source, treat as indicative) claims a bundle of a few MB against 120-200 MB for Electron, and much lower idle memory. Not measured by us.

## Why Electron stays today
- The app's security claims (hardened window, every permission denied, deep links only to our own origin, single instance) are tested against the real Electron app (`apps/desktop/scripts/test.mjs`, 12 checks). Moving would mean re-proving all of them.
- Offline verification (`@pramaan/verify`) needs Ed25519 in WebCrypto. Electron ships one known Chromium, so that works the same on every machine. With the system web view, support would depend on the user's operating system version. That has to be tested per platform before a move.
- The release pipeline (signing, auto-update) already exists for Electron.

## What would make us move
- Download size or memory becoming a real complaint, or mobile reuse (Tauri 2 also targets Android and iOS) becoming worth more than the Capacitor plan (MOB-02).

## The spike that would settle it (not done)
1. Build the same shell in Tauri 2 (window, tray, global shortcut, `pramaan://` links, single instance).
2. Run the offline verifier in the system web view on Windows 10, Windows 11, an older and a current macOS, and Ubuntu LTS; record where Ed25519 WebCrypto is missing.
3. Measure installer size, idle memory and cold start on the same machine for both shells.
4. Port the 12 security checks.
