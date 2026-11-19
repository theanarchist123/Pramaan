// Opens every page of the app as an Android phone would (Pixel-class 412x915, a small 360x640, and a wide 600x960 tablet-ish), reports anything that overflows
// sideways or is clipped, lists the offending elements, and saves a screenshot of each. Needs a RUNNING web app (and API for pages that load data).
//   node scripts/phone-audit.mjs [webUrl] [apiUrl] [--shots]
import { chromium, devices } from "playwright";
import { mkdirSync } from "node:fs";

const WEB = process.argv[2] ?? "http://localhost:3013";
const API = process.argv[3] ?? "http://localhost:8010";
const SHOTS = process.argv.includes("--shots");
mkdirSync("phone-shots", { recursive: true });

const SIZES = [
  { name: "pixel-412", width: 412, height: 915 },
  { name: "small-360", width: 360, height: 640 },
  { name: "wide-600", width: 600, height: 960 },
  // Android's "Font size" setting scales text (up to ~1.3x) and "Display size" shrinks the CSS viewport: the worst realistic combinations.
  { name: "small-360-font130", width: 360, height: 640, fontScale: 1.3 },
  { name: "narrow-320-font130", width: 320, height: 640, fontScale: 1.3 },
];

const profiles = await (await fetch(`${API}/v1/profiles?limit=3`).catch(() => ({ json: async () => [] }))).json().catch(() => []);
const slug = profiles[0]?.slug;
const ROUTES = ["/", "/directory", "/verify", "/developers", "/onboard", "/auth?mode=login", "/auth?mode=register", "/me", ...(slug ? [`/p/${slug}`] : [])];

const browser = await chromium.launch();
let problems = 0;
for (const size of SIZES) {
  const ctx = await browser.newContext({ ...devices["Pixel 7"], viewport: { width: size.width, height: size.height }, deviceScaleFactor: 2, bypassCSP: true });
  const page = await ctx.newPage();
  page.setDefaultNavigationTimeout(60000);
  for (const route of ROUTES) {
    await page.goto(`${WEB}${route}`, { waitUntil: "networkidle" }).catch(() => {});
    if (size.fontScale) await page.evaluate((f) => { document.documentElement.style.fontSize = `${f * 100}%`; }, size.fontScale);
    await page.waitForTimeout(600);
    const report = await page.evaluate((vw) => {
      const doc = document.documentElement;
      const bad = [];
      for (const el of document.querySelectorAll("body *")) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        const cs = getComputedStyle(el);
        if (cs.position === "fixed" || cs.visibility === "hidden" || cs.display === "none") continue;
        // an element inside a horizontally scrolling strip is allowed to extend past the edge
        let p = el.parentElement, inScroller = false;
        while (p && p !== document.body) {
          const o = getComputedStyle(p).overflowX;
          if (o === "auto" || o === "scroll" || o === "hidden" || o === "clip") { inScroller = true; break; }
          p = p.parentElement;
        }
        if (inScroller) continue;
        if (r.right > vw + 1 || r.left < -1) bad.push(`${el.tagName.toLowerCase()}.${String(el.className).split(" ").slice(0, 3).join(".")} [${Math.round(r.left)}..${Math.round(r.right)}] "${(el.textContent || "").trim().slice(0, 30)}"`);
      }
      // Text squeezed into a sliver: a paragraph or heading with plenty of words in a box under 120px wide wraps to one word per line (the home trust strip and the
      // verify banner did this on phones and nothing overflowed, so the check above missed it).
      for (const el of document.querySelectorAll("main p, main h1, main h2, main h3, main li")) {
        const r = el.getBoundingClientRect();
        const text = (el.textContent || "").trim();
        if (r.width === 0 || r.height === 0 || getComputedStyle(el).display === "none") continue;
        if (el.closest(".sr-only")) continue; // text for screen readers is meant to be 1px wide
        if (r.width < 120 && text.length > 24 && text.split(/\s+/).length > 3) bad.push(`${el.tagName.toLowerCase()} squeezed to ${Math.round(r.width)}px "${text.slice(0, 30)}"`);
      }
      return { scrollW: doc.scrollWidth, vw, sideways: doc.scrollWidth > vw + 1, bad: bad.slice(0, 6), badCount: bad.length };
    }, size.width);
    const flag = report.sideways || report.badCount > 0;
    if (flag) problems++;
    console.log(`${flag ? "OVERFLOW" : "ok      "} ${size.name} ${route}  scrollWidth=${report.scrollW}/${report.vw}${report.badCount ? `  ${report.badCount} element(s) past the edge` : ""}`);
    for (const b of report.bad) console.log(`            ${b}`);
    if (SHOTS) await page.screenshot({ path: `phone-shots/${size.name}-${route.replace(/[^a-z0-9]+/gi, "_") || "home"}.png`, fullPage: false });
  }
  await ctx.close();
}
await browser.close();
console.log(problems ? `\n${problems} page/size combinations overflow.` : "\nNo page overflows at any phone size.");
process.exit(problems ? 1 : 0);
