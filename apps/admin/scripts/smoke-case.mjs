// Browser test of the reviewer workbench (/case/[id]) against a RUNNING API + admin app and the LOCAL docker database.
// Reviewer signs in, opens a case from the queue, takes it, verifies a claim with the keyboard, approves, and the database agrees.
// Usage: node scripts/smoke-case.mjs [adminUrl] [apiUrl]      (API with STAFF_MFA_REQUIRED=false)
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { randomBytes } from "node:crypto";
import assert from "node:assert/strict";

const ADMIN = process.argv[2] ?? "http://localhost:3011";
const API = process.argv[3] ?? "http://localhost:8010";
mkdirSync("smoke-shots", { recursive: true });
const PASSWORD = "password123";
const tag = randomBytes(3).toString("hex");
const sql = (q) => execFileSync("docker", ["exec", "pramaan-db", "psql", "-U", "pramaan", "-d", "pramaan", "-tAc", q], { encoding: "utf8" }).trim();
const J = { "Content-Type": "application/json" };
async function register(email, name) {
  const r = await fetch(`${API}/v1/auth/register`, { method: "POST", headers: J, body: JSON.stringify({ email, password: PASSWORD, name }) });
  assert.equal(r.status, 201, `register ${email}`);
  return (await r.json()).access_token;
}

const reviewerEmail = `rv-${tag}@example.com`;
const memberEmail = `mb-${tag}@example.com`;
await register(reviewerEmail, "Smoke Reviewer");
const memberToken = await register(memberEmail, "Smoke Member");
sql(`insert into user_roles (user_id, role_key, granted_at) select id, 'reviewer', now() from users where email='${reviewerEmail}'`);
sql(`update users set email_verified_at = now() where email='${memberEmail}'`);
const auth = { Authorization: `Bearer ${memberToken}`, ...J };
const name = `Case Person ${tag}`;
const prof = await (await fetch(`${API}/v1/profiles`, { method: "POST", headers: auth, body: JSON.stringify({ full_name: name, sector: "Science", state: "Kerala", consent_public_listing: true }) })).json();
const claim = await (await fetch(`${API}/v1/profiles/${prof.id}/claims`, { method: "POST", headers: auth, body: JSON.stringify({ field: "education", value: "Studied marine biology at Cochin University" }) })).json();
assert.equal((await fetch(`${API}/v1/profiles/${prof.id}/submit`, { method: "POST", headers: auth })).status, 200, "submit for review");

const browser = await chromium.launch();
const errors = [];
const page = await (await browser.newContext({ viewport: { width: 1280, height: 1000 } })).newPage();
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error" && !/401|403|409|Failed to load resource/.test(m.text())) errors.push(`console: ${m.text().slice(0, 300)}`); });
const step = async (n, fn) => { process.stdout.write(`• ${n} … `); await fn(); console.log("ok"); };

await step("reviewer signs in and finds the case in the queue", async () => {
  await page.goto(`${ADMIN}/login`, { timeout: 90000 });
  await page.getByLabel("Email").fill(reviewerEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("link", { name }).waitFor({ timeout: 30000 });
});
await step("the case page shows the claim, documents, namesakes, and the form is closed until the case is taken", async () => {
  await page.getByRole("link", { name }).click();
  await page.getByRole("heading", { name }).waitFor({ timeout: 30000 });
  await page.getByText("Studied marine biology at Cochin University").waitFor();
  await page.getByText("People with the same name on Wikidata").waitFor();
  await page.getByText("Take the case to decide on it.").waitFor();
  assert.equal(await page.getByRole("button", { name: "Save decision" }).isDisabled(), true);
  await page.screenshot({ caret: "initial", path: "smoke-shots/case-1-before-take.png", fullPage: true });
});
await step("taking the case opens the form; j/v keys set Verify on the focused claim", async () => {
  await page.getByRole("button", { name: "Take case" }).click();
  await page.getByText("You hold this case").waitFor();
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("v");
  await page.waitForFunction(() => [...document.querySelectorAll("select")].some((s) => s.value === "verify"));
  await page.getByText("Verifying needs a note and an evidence reference.").waitFor();
});
await step("approving with a note and evidence reference saves, returns to the queue, and the database agrees", async () => {
  await page.getByLabel("What you checked").fill("Checked against the university alumni register");
  await page.getByLabel("Evidence reference").fill("https://example.org/alumni-register");
  await page.getByLabel("Outcome").selectOption("approve");
  await page.getByLabel(/^Note/).fill("Evidence checked by hand against the register");
  await page.getByRole("button", { name: "Save decision" }).click();
  await page.waitForURL(`${ADMIN}/`, { timeout: 20000 });
  assert.equal(sql(`select status from profiles where id='${prof.id}'`), "approved");
  assert.equal(sql(`select status from claims where id='${claim.id}'`), "human");
  assert.equal(sql(`select decision_basis from profiles where id='${prof.id}'`), "reviewer");
});

await browser.close();
if (errors.length) { console.error("\nBrowser errors:\n" + errors.join("\n")); process.exit(1); }
console.log("\nCase workbench smoke test passed.");
