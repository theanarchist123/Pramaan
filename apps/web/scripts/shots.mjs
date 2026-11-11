// Screenshots of key pages in both themes (before/after record). Usage: node scripts/shots.mjs [webUrl]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
const WEB = process.argv[2] ?? "http://localhost:3012";
mkdirSync("smoke-shots", { recursive: true });
const b = await chromium.launch();
for (const scheme of ["light", "dark"]) {
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: scheme });
  const p = await ctx.newPage();
  await p.addInitScript((s) => { try { localStorage.setItem("theme", s); } catch {} }, scheme);
  for (const [name, path] of [["home", "/"], ["verify", "/verify"]]) {
    await p.goto(WEB + path, { timeout: 90000 });
    await p.waitForTimeout(3500);
    await p.screenshot({ caret: "initial", path: `smoke-shots/v2-${scheme}-${name}.png` });
    console.log("shot", scheme, name);
  }
  await ctx.close();
}
await b.close();
