// Review screenshots: every public page, light + dark desktop, and a phone width. Usage: node scripts/shots-all.mjs [webUrl] [apiUrl]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
const WEB = process.argv[2] ?? "http://localhost:3012";
const API = process.argv[3] ?? "http://localhost:8010";
mkdirSync("smoke-shots/review", { recursive: true });
const people = await (await fetch(`${API}/v1/profiles?limit=5`)).json();
const certs = await (await fetch(`${API}/v1/transparency?limit=40`)).json();
const live = [];
for (const c of certs) { const v = await (await fetch(`${API}/v1/verify/${c.certificate_code}`)).json(); if (v.valid && !v.revoked) { live.push(c.certificate_code); break; } }
const pages = [["home", "/"], ["directory", "/directory"], ["profile", `/p/${people[0].slug}`], ["transparency", "/transparency"], ["developers", "/developers"], ["floor", "/mission-control"], ["result", `/verify/${live[0]}`]];
const b = await chromium.launch();
const runs = [["light", 1280, 900], ["dark", 1280, 900], ["mobile", 390, 800]];
for (const [mode, w, h] of runs) {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: mode === "dark" ? "dark" : "light" });
  const p = await ctx.newPage();
  await p.addInitScript((s) => { try { localStorage.setItem("theme", s); } catch {} }, mode === "dark" ? "dark" : "light");
  for (const [name, path] of pages) {
    try {
      await p.goto(WEB + path, { timeout: 90000 });
      await p.waitForTimeout(3000);
      await p.screenshot({ caret: "initial", path: `smoke-shots/review/${mode}-${name}.png`, fullPage: mode === "mobile" ? false : false });
      console.log("shot", mode, name);
    } catch (e) { console.log("FAILED", mode, name, e.message.slice(0, 80)); }
  }
  await ctx.close();
}
await b.close();
