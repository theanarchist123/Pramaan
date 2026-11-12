// The <pramaan-verify> widget in a real browser, on a plain static page. node scripts/smoke-widget.mjs [webUrl] [apiUrl]
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import assert from "node:assert/strict";

const WEB = process.argv[2] ?? "http://localhost:3013", API = process.argv[3] ?? "http://localhost:8010";
const sql = (q) => execFileSync("docker", ["exec", "pramaan-db", "psql", "-U", "pramaan", "-d", "pramaan", "-tAc", q], { encoding: "utf8" }).trim();
const verify = async (code) => (await fetch(`${API}/v1/verify/${code}`)).json();

const log = await (await fetch(`${API}/v1/transparency?limit=60`)).json();
let good = null, replaced = null;
for (const e of log) {
  const v = await verify(e.certificate_code);
  if (v.valid && !v.revoked && !v.superseded_by && !good) good = e.certificate_code;
  if (v.superseded_by && !replaced) replaced = e.certificate_code;
  if (good && replaced) break;
}
const revoked = sql("select code from certificates where revoked_at is not null limit 1");
assert.ok(good, "a good certificate exists to test with");

// Playwright's bundled Chromium has no Ed25519 in WebCrypto unless this flag is on (Chrome 137+, Firefox and Safari have it natively).
const browser = await chromium.launch({ args: ["--enable-experimental-web-platform-features"] });
const ctx = await browser.newContext({ bypassCSP: true });
const page = await ctx.newPage();
page.setDefaultNavigationTimeout(90000);
const demo = (code) => `${WEB}/widget-demo.html?code=${encodeURIComponent(code)}&api=${encodeURIComponent(API)}`;
const status = async () => (await page.locator("pramaan-verify").locator("css=.head").innerText()).trim();
const step = async (n, fn) => { process.stdout.write(`• ${n} … `); await fn(); console.log("ok"); };

await step("a good certificate says Authentic, checked in the visitor's browser", async () => {
  await page.goto(demo(good));
  await page.locator("pramaan-verify").getByText("Authentic").waitFor({ timeout: 30000 });
  await page.locator("pramaan-verify").getByText(/Signature checked in your browser/).waitFor();
  await page.locator("pramaan-verify").getByRole("link", { name: /full check/ }).waitFor();
});
if (revoked) await step("a revoked certificate says Revoked even though its signature is genuine", async () => {
  await page.goto(demo(revoked));
  await page.locator("pramaan-verify").getByText("Revoked", { exact: true }).waitFor({ timeout: 30000 });
});
if (replaced) await step("a replaced certificate says so", async () => {
  await page.goto(demo(replaced));
  await page.locator("pramaan-verify").getByText("Genuine, but replaced").waitFor({ timeout: 30000 });
});
await step("an unknown code says Not found", async () => {
  await page.goto(demo("PRM-ABCDEFGHJK"));
  await page.locator("pramaan-verify").getByText("Not found").waitFor({ timeout: 30000 });
});
await step("a certificate whose content was changed in transit says Not valid", async () => {
  await page.route(`${API}/v1/certificates/${good}`, async (route) => {
    const r = await route.fetch();
    const body = await r.json();
    body.payload.full_name = "Someone Else";
    await route.fulfill({ response: r, json: body });
  });
  await page.goto(demo(good));
  await page.locator("pramaan-verify").getByText("Not valid").waitFor({ timeout: 30000 });
  await page.unroute(`${API}/v1/certificates/${good}`);
});
await step("hostile text in a certificate is shown as text and never run as HTML", async () => {
  const evil = '<img src=x onerror="window.__pwned=1">';
  await page.route(`${API}/v1/certificates/${good}`, async (route) => {
    const r = await route.fetch();
    const body = await r.json();
    body.payload.full_name = evil;
    await route.fulfill({ response: r, json: body });
  });
  await page.goto(demo(good));
  await page.locator("pramaan-verify").getByText("Not valid").waitFor({ timeout: 30000 });
  assert.equal(await page.evaluate(() => window.__pwned), undefined, "no script ran");
  assert.equal(await page.locator("pramaan-verify").locator("css=img").count(), 0, "no element was created from the text");
  await page.locator("pramaan-verify").getByText(evil).waitFor(); // it is displayed literally
  await page.unroute(`${API}/v1/certificates/${good}`);
});
await step("without a code or api it says what is missing instead of failing silently", async () => {
  await page.goto(`${WEB}/widget-demo.html`);
  await page.locator("pramaan-verify").getByText("Missing settings").waitFor({ timeout: 30000 });
});
await browser.close();
console.log("\nWidget smoke test passed.");
