// Browser test of the Verify pages: the five verdicts, integrated forge mode, the segmented code input (with the refused-
// character hint), recent checks, and the offline file check. Needs a RUNNING API + web app and the LOCAL docker database.
//   node scripts/smoke-verify.mjs [webUrl] [apiUrl]
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { randomBytes } from "node:crypto";
import assert from "node:assert/strict";

const WEB = process.argv[2] ?? "http://localhost:3012";
const API = process.argv[3] ?? "http://localhost:8010";
const OUT = "smoke-shots";
mkdirSync(OUT, { recursive: true });
const tag = randomBytes(3).toString("hex");
const PASSWORD = "password123";
const sql = (q) => execFileSync("docker", ["exec", "pramaan-db", "psql", "-U", "pramaan", "-d", "pramaan", "-tAc", q], { encoding: "utf8" }).trim();
const J = { "Content-Type": "application/json" };
const post = async (path, token, body) => (await fetch(`${API}${path}`, { method: "POST", headers: { ...J, ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: body ? JSON.stringify(body) : undefined }));
const register = async (email) => (await (await post("/v1/auth/register", null, { email, password: PASSWORD, name: "Smoke" })).json()).access_token;

// ---- seed: one profile with a certificate, a second certificate replacing a first, and a revoked one ------------------------
const admin = await register(`va-${tag}@example.com`);
sql(`update users set role='admin' where email='va-${tag}@example.com'`);

async function certified(label, extraClaim) {
  const email = `vm-${label}-${tag}@example.com`;
  const member = await register(email);
  sql(`update users set email_verified_at = now() where email='${email}'`);
  const prof = await (await post("/v1/profiles", member, { full_name: `Verify ${label} ${tag}`, sector: "Science", state: "Kerala", consent_public_listing: true })).json();
  const claim = await (await post(`/v1/profiles/${prof.id}/claims`, member, { field: "award", value: `Sagar Samman ${label}` })).json();
  await post(`/v1/profiles/${prof.id}/submit`, member);
  const ok = { reason: "Checked against the published honours list", evidence_ref: "https://example.org/honours" };
  await post(`/v1/admin/claims/${claim.id}/verify`, admin, ok);
  await post(`/v1/admin/profiles/${prof.id}/status`, admin, { status: "approved" });
  const cert = await (await post(`/v1/profiles/${prof.id}/certificate`, member)).json();
  assert.ok(cert.code, `certificate issued for ${label}`);
  return { member, prof, cert, ok };
}
const valid = await certified("valid");
const replaced = await certified("replaced");
{
  const extra = await (await post(`/v1/profiles/${replaced.prof.id}/claims`, replaced.member, { field: "education", value: "Studied at Cochin University" })).json();
  await post(`/v1/admin/claims/${extra.id}/verify`, admin, replaced.ok);
  assert.ok((await (await post(`/v1/profiles/${replaced.prof.id}/certificate`, replaced.member)).json()).code, "second certificate issued");
}
const revoked = await certified("revoked");
sql(`update certificates set revoked_at = now() where code = '${revoked.cert.code}'`);

const browser = await chromium.launch();
const errors = [];
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error" && !/404|Failed to load resource/.test(m.text())) errors.push(`console: ${m.text()}`); });
const step = async (name, fn) => { process.stdout.write(`• ${name} … `); await fn(); console.log("ok"); };
const banner = () => page.getByRole("status").first();

await step("entry page is never empty: what we check, recent checks, scanner/file options", async () => {
  await page.goto(`${WEB}/verify`);
  await page.getByRole("heading", { name: "Verify a certificate" }).waitFor();
  await page.getByText("Content fingerprint").waitFor();
  await page.getByText("Revocation").first().waitFor();
  await page.getByText("Nothing yet.").waitFor();
  await page.getByText(/Drop a certificate file/).waitFor();
  await page.screenshot({ caret: "initial", path: `${OUT}/verify-1-entry.png` });
});
await step("the code boxes refuse characters a code never contains, and explain why", async () => {
  await page.getByLabel("Character 1 of 10").fill("O");
  await page.getByText(/never appears in a code/).waitFor();
  await page.getByLabel("Character 1 of 10").fill("");
});
await step("pasting a whole code fills the boxes and submits", async () => {
  await page.getByLabel("Character 1 of 10").click();
  await page.evaluate(async (code) => {
    const el = document.querySelector('[aria-label="Character 1 of 10"]');
    const dt = new DataTransfer(); dt.setData("text", code);
    el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
  }, valid.cert.code);
  await page.waitForURL(`**/verify/${valid.cert.code}`);
});

await step("VALID: 'Authentic', five checks cascade, one certificate on the page", async () => {
  await banner().getByRole("heading", { name: "Authentic" }).waitFor();
  const list = page.getByRole("list", { name: "How we checked" });
  await list.getByText(/Found at position/).waitFor();
  await list.getByText("Confirmed it has not been revoked").waitFor();
  assert.equal(await page.locator("#certificate").count(), 1, "exactly one certificate (no second copy for forge mode)");
  // the redesigned certificate: sentence-case title, a status in words beside each claim, and the honest QR note (no tracked all-caps, no "tamper-proof" claim)
  const cert = page.locator("#certificate");
  await cert.getByText("Certificate of verified record").waitFor();
  await cert.getByText("Registry of Record").waitFor();
  await cert.getByText("Printed copies can be altered; the online record cannot.").waitFor();
  assert.equal(await cert.getByText(/CERTIFICATE OF VERIFIED ACHIEVEMENT/).count(), 0, "the old tracked all-caps title is gone");
  assert.equal(await cert.getByText(/Confirmed by a reviewer/).count() >= 1, true, "each claim carries its status in words");
  await page.screenshot({ caret: "initial", path: `${OUT}/verify-2-valid.png`, fullPage: true });
});
await step("FORGE: editing a letter on the page breaks the signature and the checks re-run", async () => {
  await page.getByRole("button", { name: "Edit as a forger" }).click();
  await page.getByLabel("Achievement 1").fill("Padma Vibhushan");
  await page.getByText("Forgery detected").waitFor();
  await page.getByText(/does not match|edited after issuance/i).first().waitFor();
  assert.equal(await page.locator("#certificate").count(), 1, "still one certificate in forge mode");
  await page.screenshot({ caret: "initial", path: `${OUT}/verify-3-forged.png`, fullPage: true });
  await page.getByRole("button", { name: "Reset" }).click();
  await page.getByText("Nothing changed yet").waitFor();
});
await step("REPLACED: genuine, but says a newer certificate replaced it, with a link", async () => {
  await page.goto(`${WEB}/verify/${replaced.cert.code}`);
  await banner().getByRole("heading", { name: "Genuine, but replaced" }).waitFor();
  await banner().getByRole("link", { name: "View the newer certificate" }).waitFor();
  await page.getByText("A newer certificate has taken its place.").waitFor(); // the state is ON the certificate, in words
  await page.screenshot({ caret: "initial", path: `${OUT}/verify-4-replaced.png` });
});
await step("REVOKED: says so and overprints the paper", async () => {
  await page.goto(`${WEB}/verify/${revoked.cert.code}`);
  await banner().getByRole("heading", { name: "Revoked" }).waitFor();
  await page.getByText("Revoked", { exact: true }).nth(1).waitFor();
  await page.getByText("The registry has withdrawn this certificate.").waitFor();
  await page.screenshot({ caret: "initial", path: `${OUT}/verify-5-revoked.png` });
});
await step("NOT FOUND: says so, and offers the likely correction for a look-alike character", async () => {
  await page.goto(`${WEB}/verify/PRM-ABCDEFGHJ0`);
  await banner().getByRole("heading", { name: "Not found" }).waitFor();
  await page.getByText(/never contain 0, 1, I, L, O or U/).waitFor();
  await page.screenshot({ caret: "initial", path: `${OUT}/verify-6-notfound.png` });
});
await step("recent checks lists what was checked, on this device only, and can be cleared", async () => {
  await page.goto(`${WEB}/verify`);
  await page.getByRole("link", { name: new RegExp(valid.cert.code) }).waitFor();
  await page.getByRole("button", { name: "Clear" }).click();
  await page.getByText("Nothing yet.").waitFor();
});
await step("ALTERED file: the offline check refuses an edited certificate file", async () => {
  const res = await fetch(`${API}/v1/certificates/${valid.cert.code}`);
  const cert = await res.json();
  cert.payload.full_name = "Someone Else";
  await page.goto(`${WEB}/verify`);
  await page.locator('input[type="file"]').setInputFiles({ name: "edited.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(cert)) });
  await page.getByText(/edited|does not match/i).first().waitFor();
});
await step("GENUINE file: checked on this device (or says plainly that this browser lacks Ed25519)", async () => {
  const cert = await (await fetch(`${API}/v1/certificates/${valid.cert.code}`)).json();
  await page.locator('input[type="file"]').setInputFiles({ name: "cert.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(cert)) });
  await page.getByText(/Authentic: |does not support Ed25519/).first().waitFor();
});
await step("REDUCED MOTION: with the in-app switch on, every check is shown at once", async () => {
  await page.goto(`${WEB}/verify/${valid.cert.code}`);
  await page.getByRole("button", { name: "Account and settings" }).click(); // the switch lives in the account menu now
  await page.getByRole("menuitemcheckbox", { name: "Reduce motion" }).click();
  await page.keyboard.press("Escape");
  await page.reload();
  // Wait (generously) for the first check to appear; with reduced motion the rest must already be there, not arriving one by one.
  const list = page.getByRole("list", { name: "How we checked" });
  await list.getByRole("listitem").first().waitFor({ timeout: 30000 });
  assert.equal(await list.getByRole("listitem").count(), 4, "all four checks are shown at once");
});

await browser.close();
if (errors.length) { console.error("\nBrowser errors:\n" + errors.join("\n")); process.exit(1); }
console.log("\nVerify smoke test passed.");
