"use strict";
// Auto-update for the installed app. Updates are downloaded from the release feed in package.json ("build.publish")
// and electron-updater verifies each download against the signed manifest (latest*.yml) AND, on Windows, the
// installer's code-signing publisher, so a tampered file is refused. Never runs in dev or in tests.

const HOURS = 60 * 60 * 1000;

function startAutoUpdates(app, log = console) {
  if (!app.isPackaged || process.env.PRAMAAN_TEST === "1" || process.env.PRAMAAN_NO_UPDATE === "1") return null;
  let autoUpdater;
  try {
    ({ autoUpdater } = require("electron-updater"));
  } catch (err) {
    log.warn("auto-update unavailable:", err.message);
    return null;
  }
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true; // applied the next time the user quits: never interrupts their work
  autoUpdater.allowDowngrade = false;
  autoUpdater.on("error", (err) => log.warn("update check failed:", err && err.message));
  const check = () => autoUpdater.checkForUpdates().catch((err) => log.warn("update check failed:", err.message));
  setTimeout(check, 15 * 1000);
  const timer = setInterval(check, 6 * HOURS);
  timer.unref();
  return autoUpdater;
}

module.exports = { startAutoUpdates };
