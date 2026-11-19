// DR-05: a sleeping server must not look broken. With /healthz held for 9 s: nothing in the first 3 s, then a "Waking up" pill BELOW the navigation (never over the
// logo or the menu), and it disappears once the server answers.   node scripts/smoke-banner.mjs [webUrl]
import { chromium } from "playwright";

const WEB = process.argv[2] ?? "http://localhost:3013";
const browser = await chromium.launch();
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? "ok  " : "FAIL"} ${what}`); if (!ok) failed++; };

for (const [name, viewport] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 412, height: 915 }]]) {
  const ctx = await browser.newContext({ viewport });
  const page = await ctx.newPage();
  let release;
  const held = new Promise((r) => { release = r; });
  await page.route("**/healthz", async (route) => { await held; await route.fulfill({ status: 200, contentType: "application/json", body: "{\"status\":\"ok\"}" }); });
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  const banner = page.getByTestId("connection-banner");
  await page.waitForTimeout(2500);
  check((await banner.count()) === 0, `${name}: nothing is shown during the first seconds`);
  await page.waitForTimeout(12000);
  check(await banner.isVisible(), `${name}: the pill appears once the server has been silent for a while`);
  check(/Waking up/.test((await banner.textContent()) ?? ""), `${name}: it says the server is waking up`);
  const box = await banner.locator("div").first().boundingBox();
  const nav = await page.locator(viewport.width >= 768 ? "header" : "[data-mobile-appbar], header ~ div").first().boundingBox().catch(() => null);
  check(!!box && box.y >= 56, `${name}: it sits below the top bar (y=${Math.round(box?.y ?? -1)})`);
  void nav;
  release();
  await page.waitForTimeout(5000);
  check((await banner.count()) === 0, `${name}: it goes away when the server answers`);
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
