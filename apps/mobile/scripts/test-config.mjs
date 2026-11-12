// The Capacitor config's safety rules, checked with node. Run: node scripts/test-config.mjs
// (A real device build needs the Android SDK and your Firebase file: see README.md. This only guards the settings that matter for safety.)
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";

const cfg = JSON.parse(readFileSync(new URL("../capacitor.config.json", import.meta.url), "utf8"));
const host = new URL(cfg.server.url).host;

assert.equal(cfg.server.url.startsWith("https://"), true, "the app loads the site over https only");
assert.equal(cfg.server.cleartext, false, "no cleartext traffic");
assert.deepEqual(cfg.server.allowNavigation, [host], "the app may navigate only inside its own site; everything else opens in the browser");
assert.equal(cfg.android.allowMixedContent, false);
assert.equal(cfg.android.webContentsDebuggingEnabled, false, "web debugging is off in the shipped app");
assert.ok(existsSync(new URL("../www/offline.html", import.meta.url)), "an offline page ships inside the app");
assert.equal(cfg.appId, "in.pramaan.app");
const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
assert.ok(Object.keys(pkg.dependencies).every((d) => d.startsWith("@capacitor/")), "no dependencies besides Capacitor");
console.log("mobile config: 9 checks passed");
