"use strict";
// Which app this is (DSK-04): the member app, or the staff console build. Pure, so it can be tested without Electron.
//
// The console is the staff admin site in its own window with its own data folder (separate cookies from the member app) and a queue badge. It is chosen ONLY
// by an explicit switch: the environment (PRAMAAN_VARIANT=console), the --console flag, or `pramaanVariant` baked into a console build's package.json. An
// unknown value always means the member app. The console has no pramaan:// links and no clipboard shortcut: it is a work tool, not a verifier.

const CONSOLE_DEFAULT_URL = "http://localhost:3000/staff";
const BASE_TITLE = "Pramaan staff console";

function pickVariant(env, argv, pkg) {
  const asked = (env && env.PRAMAAN_VARIANT) || (Array.isArray(argv) && argv.includes("--console") ? "console" : "") || (pkg && pkg.pramaanVariant) || "";
  if (asked !== "console") return { name: "member", title: "Pramaan", url: null, dataSuffix: "", deepLinks: true, clipboard: true, badge: false };
  const url = String((env && env.PRAMAAN_CONSOLE_URL) || (pkg && pkg.pramaanConsoleUrl) || CONSOLE_DEFAULT_URL).replace(/\/$/, "");
  return { name: "console", title: BASE_TITLE, url, dataSuffix: "-console", deepLinks: false, clipboard: false, badge: true };
}

/** The number of open review cases in an /v1/admin/overview answer. Anything unexpected is zero: a badge must never show a made-up number. */
function queueBadge(overview) {
  const n = overview && overview.queue && overview.queue.open;
  return Number.isInteger(n) && n > 0 ? Math.min(n, 999) : 0;
}

function badgeLabel(n) {
  return n > 0 ? `${BASE_TITLE}: ${n} open` : BASE_TITLE;
}

module.exports = { pickVariant, queueBadge, badgeLabel, BASE_TITLE };
