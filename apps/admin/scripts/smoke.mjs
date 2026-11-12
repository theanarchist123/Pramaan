// End-to-end smoke test of the staff console against a RUNNING API + admin app and the LOCAL docker database.
//   sign-in -> authenticator set-up -> review queue -> a Reviewer is refused (403) on a forbidden action.
//
// Prerequisites (see README in this folder's parent):
//   docker compose up -d db
//   API:    ENVIRONMENT=development STAFF_MFA_REQUIRED=true  (DATABASE_URL = the local docker db), port 8000
//   Admin:  pnpm --filter admin dev  (port 3001)
// Usage:  node scripts/smoke.mjs [adminUrl] [apiUrl]
import { chromium } from "playwright";
import { createHmac, randomBytes } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import assert from "node:assert/strict";

const ADMIN = process.argv[2] ?? "http://localhost:3001";
const API = process.argv[3] ?? "http://localhost:8000";
const OUT = "smoke-shots";
mkdirSync(OUT, { recursive: true });
const PASSWORD = "password123";
const tag = randomBytes(3).toString("hex");

// --- helpers ------------------------------------------------------------------------------------------------------
const sql = (q) => execFileSync("docker", ["exec", "pramaan-db", "psql", "-U", "pramaan", "-d", "pramaan", "-tAc", q], { encoding: "utf8" }).trim();

function totp(secretB32, at = Date.now()) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of secretB32.replace(/=+$/, "")) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 1000 / 30)));
  const mac = createHmac("sha1", key).update(counter).digest();
  const o = mac[mac.length - 1] & 0xf;
  return String(((mac.readUInt32BE(o) & 0x7fffffff) % 1_000_000)).padStart(6, "0");
}

async function register(email, name) {
  const r = await fetch(`${API}/v1/auth/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: PASSWORD, name }) });
  assert.equal(r.status, 201, `register ${email}`);
  return (await r.json()).access_token;
}

const step = async (name, fn) => {
  process.stdout.write(`• ${name} … `);
  await fn();
  console.log("ok");
};

// --- seed: an admin, a reviewer, and one case waiting in the queue ---------------------------------------------------
const adminEmail = `admin-${tag}@example.com`;
const reviewerEmail = `reviewer-${tag}@example.com`;
const memberEmail = `member-${tag}@example.com`;
await register(adminEmail, "Smoke Admin");
await register(reviewerEmail, "Smoke Reviewer");
const memberToken = await register(memberEmail, "Smoke Member");
sql(`update users set role='admin' where email='${adminEmail}'`);
sql(`insert into user_roles (user_id, role_key, granted_at) select id, 'reviewer', now() from users where email='${reviewerEmail}'`);
sql(`update users set email_verified_at = now() where email='${memberEmail}'`);
const auth = { Authorization: `Bearer ${memberToken}`, "Content-Type": "application/json" };
const prof = await (await fetch(`${API}/v1/profiles`, { method: "POST", headers: auth, body: JSON.stringify({ full_name: `Smoke Person ${tag}`, sector: "Science", state: "Kerala", consent_public_listing: true }) })).json();
await fetch(`${API}/v1/profiles/${prof.id}/claims`, { method: "POST", headers: auth, body: JSON.stringify({ field: "education", value: "Studied marine biology at Cochin University" }) });
assert.equal((await fetch(`${API}/v1/profiles/${prof.id}/submit`, { method: "POST", headers: auth })).status, 200, "submit for review");

const browser = await chromium.launch();
const errors = [];
const watch = (page) => {
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error" && !/403|401/.test(m.text())) errors.push(`console: ${m.text()}`); });
};

async function signInAndEnrol(context, email) {
  const page = await context.newPage();
  watch(page);
  await page.goto(`${ADMIN}/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/security"); // MFA is mandatory: a first sign-in goes straight to set-up
  await page.getByRole("button", { name: "Set up authenticator" }).click();
  const secret = (await page.locator("code").first().textContent()).trim();
  await page.getByLabel("6-digit code").fill(totp(secret));
  await page.getByRole("button", { name: "Finish set-up" }).click();
  await page.getByText("Authenticator app: set up").waitFor();
  const codes = (await page.getByTestId("recovery-codes").textContent()).trim().split(/\s+/);
  assert.equal(codes.length, 10, "ten recovery codes are shown once");
  await page.getByRole("button", { name: "I have saved them" }).click();
  return { page, secret, codes };
}

// --- 1. the admin: sign-in, set-up, queue -----------------------------------------------------------------------------
const adminCtx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
let adminPage;
await step("staff sign-in lands on authenticator set-up (MFA is mandatory)", async () => {
  ({ page: adminPage } = await signInAndEnrol(adminCtx, adminEmail));
  await adminPage.screenshot({ path: `${OUT}/admin-1-security.png` });
});
await step("review queue shows the waiting case with its reason codes", async () => {
  await adminPage.getByRole("link", { name: "← Review queue" }).click();
  await adminPage.getByRole("heading", { name: "Review queue" }).waitFor();
  const row = adminPage.getByRole("row", { name: new RegExp(`Smoke Person ${tag}`) });
  await row.waitFor();
  await row.getByText("USER_REQUESTED").waitFor();
  await adminPage.screenshot({ path: `${OUT}/admin-2-queue.png` });
});
await step("the admin can take the case", async () => {
  const row = adminPage.getByRole("row", { name: new RegExp(`Smoke Person ${tag}`) });
  await row.getByRole("button", { name: "Take case" }).click();
  await row.getByText("Being reviewed").waitFor();
});

// --- 2. a Reviewer: also enrols, can read the queue, and is refused a forbidden action ---------------------------------
const reviewerCtx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
let reviewerPage;
await step("a Reviewer signs in, enrols, and sees the queue", async () => {
  ({ page: reviewerPage } = await signInAndEnrol(reviewerCtx, reviewerEmail));
  await reviewerPage.getByRole("link", { name: "← Review queue" }).click();
  await reviewerPage.getByRole("heading", { name: "Review queue" }).waitFor();
  await reviewerPage.getByText(/Your permissions: .*review\.read/).waitFor();
});
await step("a Reviewer gets 403 when revoking a certificate, changing a setting and revealing PII", async () => {
  const call = (path, body) =>
    reviewerPage.evaluate(async ({ api, path, body }) => {
      const r = await fetch(`${api}${path}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      return { status: r.status, body: await r.json().catch(() => null) };
    }, { api: API, path, body });
  const reason = "Agreed in the weekly risk review";
  for (const [name, path, body] of [
    ["revoke", "/v1/admin/certificates/PRM-NOPE/revoke", { reason }],
    ["setting", "/v1/admin/settings/award_claims_need_human", { value: false, reason }],
    ["pii reveal", "/v1/admin/pii/reveal", { profile_id: prof.id, reason }],
  ]) {
    const r = await call(path, body);
    assert.equal(r.status, 403, `${name} should be forbidden, got ${r.status}`);
    assert.match(JSON.stringify(r.body), /does not allow/, name);
  }
  await reviewerPage.screenshot({ path: `${OUT}/admin-3-reviewer.png` });
});
await step("the staff cookie does not log the browser into the member API", async () => {
  const s = await reviewerPage.evaluate(async (api) => (await fetch(`${api}/v1/auth/me`, { credentials: "include" })).status, API);
  assert.equal(s, 401);
});

await browser.close();
if (errors.length) {
  console.error("\nBrowser errors:\n" + errors.join("\n"));
  process.exit(1);
}
console.log("\nAdmin smoke test passed.");
