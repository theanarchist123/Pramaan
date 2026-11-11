// Screenshots of key pages in the dark theme (for the before/after record). Usage: node scripts/shots-dark.mjs [webUrl]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
const WEB = process.argv[2] ?? "http://localhost:3012";
mkdirSync("smoke-shots", { recursive: true });
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: "dark" });
const p = await ctx.newPage();
await p.addInitScript(() => { try { localStorage.setItem("theme", "dark"); } catch {} });
for (const [name, path] of [["dark-home", "/"], ["dark-directory", "/directory"], ["dark-verify", "/verify"]]) {
  await p.goto(WEB + path, { timeout: 90000 });
  await p.waitForTimeout(2500);
  await p.screenshot({ caret: "initial", path: `smoke-shots/${name}.png`, fullPage: false });
  console.log("shot", name);
}
await b.close();
