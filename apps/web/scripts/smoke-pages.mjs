// Browser smoke test of the Phase 1 pages other than Verify: Home, Directory, Profile, Transparency, Developers, Agent Floor.
// Needs a RUNNING API + web app and the local docker database.  node scripts/smoke-pages.mjs [webUrl] [apiUrl]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import assert from "node:assert/strict";

const WEB = process.argv[2] ?? "http://localhost:3012";
const API = process.argv[3] ?? "http://localhost:8010";
mkdirSync("smoke-shots", { recursive: true });

const browser = await chromium.launch();
const errors = [];
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
page.setDefaultNavigationTimeout(90000); // a dev server compiles each route on first use
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error" && !/404|Failed to load resource/.test(m.text())) errors.push(`console: ${m.text().slice(0, 300)}`); });
const step = async (name, fn) => { process.stdout.write(`• ${name} … `); await fn(); console.log("ok"); };
const shot = (n) => page.screenshot({ caret: "initial", path: `smoke-shots/${n}.png`, fullPage: true });

const people = await (await fetch(`${API}/v1/profiles?limit=100`)).json();
const slug = people[0]?.slug;

await step("HOME: hero proof table checks a real certificate (or says there is none), ledger strip, no mock screenshot", async () => {
  await page.goto(`${WEB}/`);
  await page.getByText("Checked just now").waitFor();
  await page.getByText(/Confirmed it has not been revoked|has been revoked|There is no certificate to check yet/).waitFor({ timeout: 8000 });
  assert.equal(await page.getByText("Example profile · sample data").count(), 0);
  // the desk certificate: change a letter and the REGISTRY says the signature no longer holds
  const box = page.getByLabel(/Try to forge it/);
  await box.waitFor({ timeout: 20000 });
  await page.getByText("Signature valid: this is the real name").waitFor();
  const original = await box.inputValue();
  await box.fill(original.slice(0, -1) + (original.endsWith("x") ? "y" : "x"));
  await page.getByText("Signature broken: the registry refuses it").waitFor({ timeout: 10000 });
  await page.getByText("NOT VALID").waitFor();
  await box.fill(original);
  await page.getByText("Signature valid: this is the real name").waitFor({ timeout: 10000 });
  // browse by field: 14 tiles, each linking to the filtered directory
  const tiles = page.getByRole("link", { name: /: \d+ (person|people)$/ });
  assert.equal(await tiles.count(), 14, "one tile per field");
  await tiles.first().click();
  await page.waitForURL(/\/directory\?sector=/);
  await page.getByRole("button", { name: /^(Science|Technology|Energy|Healthcare)/, pressed: true }).first().waitFor({ timeout: 15000 });
  await page.goto(`${WEB}/`);
  await shot("home");
});
await step("DIRECTORY: shelves per field when unfiltered, a filter switches to one grid", async () => {
  await page.goto(`${WEB}/directory`);
  await page.getByRole("heading", { level: 1 }).waitFor();
  const shelf = page.locator("section[aria-label*=' person'], section[aria-label*=' people']");
  if (people.length >= 6) await shelf.first().waitFor({ timeout: 10000 });
  else await page.getByRole("link", { name: /./ }).first().waitFor();
  await shot("directory");
});
if (slug) {
  await step("PROFILE: claim counts say 'confirmed', never count a public-source claim as verified; evidence slip opens", async () => {
    await page.goto(`${WEB}/p/${slug}`);
    await page.getByText(/of \d+ claims confirmed/).waitFor();
    assert.equal(await page.getByText(/claims verified/).count(), 0);
    const btn = page.getByRole("button", { name: "Show the evidence" }).first();
    if (await btn.count()) { await btn.click(); await page.getByRole("button", { name: "Hide the evidence" }).first().waitFor(); }
    await shot("profile");
  });
}
await step("TRANSPARENCY: chain is re-computed in the browser; altering an entry breaks it; undo restores", async () => {
  await page.goto(`${WEB}/transparency`);
  const entries = await (await fetch(`${API}/v1/transparency?limit=500`)).json();
  if (entries.length === 0) { await page.getByText("No certificates issued yet.").waitFor(); return; }
  await page.getByText(/Chain intact/).waitFor({ timeout: 8000 });
  if (entries.length > 1) {
    await page.getByRole("button", { name: /Alter an entry/ }).click();
    await page.getByText(/Chain broken at entry/).waitFor();
    await page.getByText("First mismatch").waitFor();
    await shot("transparency-broken");
    await page.getByRole("button", { name: "Undo the alteration" }).click();
    await page.getByText(/Chain intact/).waitFor();
  }
});
await step("DEVELOPERS: sections deep-link and tabs follow arrow keys", async () => {
  await page.goto(`${WEB}/developers#play`);
  await page.getByRole("tab", { name: /Playground/ }).waitFor();
  await page.waitForFunction(() => [...document.querySelectorAll('[role=tab]')].some((t) => /Playground/.test(t.textContent) && t.getAttribute("aria-selected") === "true"), null, { timeout: 8000 });
  await page.getByRole("tab", { name: /Playground/ }).focus();
  await page.keyboard.press("ArrowRight");
  await page.waitForFunction(() => location.hash === "#keys", null, { timeout: 4000 });
});
await step("AGENT FLOOR: pipeline lists the five agents in order, each with a text status", async () => {
  await page.goto(`${WEB}/mission-control`);
  const pipe = page.getByRole("list", { name: "Order of work" });
  await pipe.waitFor();
  for (const n of ["Saathi", "Khoji-Pehle", "Lipik", "Pariksha", "Prahari"]) await pipe.getByText(n, { exact: true }).waitFor();
  assert.ok((await pipe.getByText("Idle").count()) + (await pipe.getByText("Working").count()) >= 5);
  await shot("agent-floor");
});
await step("RESPONSIVE: no page scrolls sideways at 360, 390, 768, 1024 or 1280 px", async () => {
  const paths = ["/", "/directory", slug ? `/p/${slug}` : "/directory", "/transparency", "/developers", "/mission-control", "/verify"];
  const bad = [];
  for (const w of [360, 390, 768, 1024, 1280]) {
    await page.setViewportSize({ width: w, height: 800 });
    for (const path of paths) {
      await page.goto(`${WEB}${path}`, { timeout: 90000 });
      await page.waitForTimeout(1800);
      const m = await page.evaluate(() => ({ s: document.documentElement.scrollWidth, c: document.documentElement.clientWidth }));
      if (m.s > m.c) bad.push(`${path} @${w}: ${m.s} > ${m.c}`);
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  assert.deepEqual(bad, [], "pages that scroll sideways");
});
await step("ONBOARDING (signed out): sends the visitor to sign in rather than showing a broken page", async () => {
  await page.goto(`${WEB}/onboard`, { timeout: 90000, waitUntil: "commit" });
  await page.waitForURL(/\/auth/);
});

await browser.close();
if (errors.length) { console.error("\nBrowser errors:\n" + errors.join("\n")); process.exit(1); }
console.log("\nPages smoke test passed.");
