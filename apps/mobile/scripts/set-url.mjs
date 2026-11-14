// Point the app at your deployed site, then rebuild:   node scripts/set-url.mjs https://your-domain.example
// For a quick test over your own Wi-Fi (never for a shared build):  node scripts/set-url.mjs http://192.168.1.20:3000 --dev
import { readFileSync, writeFileSync } from "node:fs";

const [, , raw, flag] = process.argv;
if (!raw) {
  console.error("Usage: node scripts/set-url.mjs <https://your-site> [--dev]");
  process.exit(2);
}
let url;
try {
  url = new URL(raw);
} catch {
  console.error(`Not a valid URL: ${raw}`);
  process.exit(2);
}
const dev = flag === "--dev";
if (url.protocol !== "https:" && !(dev && url.protocol === "http:")) {
  console.error("Use an https:// address. (http:// is allowed only with --dev, for testing on your own network.)");
  process.exit(2);
}
const file = new URL("../capacitor.config.json", import.meta.url);
const cfg = JSON.parse(readFileSync(file, "utf8"));
cfg.server.url = url.origin;
cfg.server.allowNavigation = [url.host];
cfg.server.cleartext = dev;
writeFileSync(file, JSON.stringify(cfg, null, 2) + "\n");
console.log(`App now loads ${url.origin}${dev ? "  (DEV build: plain http allowed; do not share this APK)" : ""}\nNext: pnpm sync, then pnpm build:debug`);
