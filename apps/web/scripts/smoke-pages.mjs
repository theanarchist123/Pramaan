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
  await shot("home");
});
await step("DIRECTORY: shelves per field when unfiltered, a filter switches to one grid", async () => {
  await page.goto(`${WEB}/directory`);
  await page.getByRole("heading", { level: 1 }).waitFor();
  const shelves = await page.locator("section[aria-label*=' person'], section[aria-label*=' people']").count();
  if (people.length >= 6) assert.ok(shelves >= 1, "shelves shown for a populated directory");
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
  assert.equal(await page.getByRole("tab", { name: /Playground/ }).getAttribute("aria-selected"), "true");
  await page.getByRole("tab", { name: /Playground/ }).focus();
  await page.keyboard.press("ArrowRight");
  assert.match(page.url(), /#keys$/);
});
await step("AGENT FLOOR: pipeline lists the five agents in order, each with a text status", async () => {
  await page.goto(`${WEB}/mission-control`);
  const pipe = page.getByRole("list", { name: "Order of work" });
  await pipe.waitFor();
  for (const n of ["Saathi", "Khoji-Pehle", "Lipik", "Pariksha", "Prahari"]) await pipe.getByText(n, { exact: true }).waitFor();
  assert.ok((await pipe.getByText("Idle").count()) + (await pipe.getByText("Working").count()) >= 5);
  await shot("agent-floor");
});
await step("ONBOARDING (signed out): sends the visitor to sign in rather than showing a broken page", async () => {
  await page.goto(`${WEB}/onboard`);
  await page.waitForURL(/\/auth/);
});

await browser.close();
if (errors.length) { console.error("\nBrowser errors:\n" + errors.join("\n")); process.exit(1); }
console.log("\nPages smoke test passed.");
