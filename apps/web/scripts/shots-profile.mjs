// Profile with a REAL approved cover photo (taken from the database and fed to the page), desktop + phone. node scripts/shots-profile.mjs [webUrl] [apiUrl]
import { chromium } from "playwright";
import { readFileSync, mkdirSync } from "node:fs";
mkdirSync("smoke-shots", { recursive: true });
const WEB = process.argv[2] ?? "http://localhost:3013", API = process.argv[3] ?? "http://localhost:8010";
const imgs = JSON.parse(readFileSync(new URL("./_img.json", import.meta.url), "utf8"));
const people = await (await fetch(`${API}/v1/profiles?limit=5`)).json();
const b = await chromium.launch();
for (const [name, w, h] of [["desktop", 1280, 900], ["mobile", 390, 800]]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h } });
  const p = await ctx.newPage();
  // the profile page is rendered on the server, so the cover comes from the browser-side SectorImage request: answer it with the real approved photo
  await p.route("**/v1/images/sector/**", (r) => r.fulfill({ json: [...imgs.cover, ...imgs.tile] }));
  await p.goto(`${WEB}/p/${people[0].slug}`);
  await p.waitForTimeout(5000);
  await p.screenshot({ path: `smoke-shots/profile-cover-${name}.png` });
  const av = await p.evaluate(() => { const a = document.querySelector("header [aria-hidden=true].rounded-full"); const r = a?.getBoundingClientRect(); const f = document.querySelector("header figcaption")?.getBoundingClientRect(); return { avatarTop: r && Math.round(r.top), avatarBottom: r && Math.round(r.bottom), creditLeft: f && Math.round(f.left), creditRight: f && Math.round(f.right) }; });
  console.log(name, JSON.stringify(av));
  await ctx.close();
}
await b.close();
