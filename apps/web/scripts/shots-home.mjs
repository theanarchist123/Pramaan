import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
mkdirSync("smoke-shots/review", { recursive: true });
const WEB = process.argv[2] ?? "http://localhost:3012";
const b = await chromium.launch();
for (const [mode, w, h, scheme] of [["light", 1280, 900, "light"], ["dark", 1280, 900, "dark"], ["mobile", 390, 800, "light"]]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme });
  const p = await ctx.newPage();
  await p.addInitScript((s) => { try { localStorage.setItem("theme", s); } catch {} }, scheme);
  await p.goto(WEB + "/", { timeout: 90000 });
  await p.waitForTimeout(5000);
  await p.screenshot({ caret: "initial", path: `smoke-shots/review/home3-${mode}.png`, fullPage: true });
  console.log("shot", mode);
  await ctx.close();
}
await b.close();
