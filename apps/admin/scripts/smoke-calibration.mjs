// Calibration report page in a real browser: an auditor sees it; a reviewer is not offered it. node scripts/smoke-calibration.mjs [adminUrl] [apiUrl]
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import assert from "node:assert/strict";
const ADMIN = process.argv[2] ?? "http://localhost:3011", API = process.argv[3] ?? "http://localhost:8010";
const tag = randomBytes(3).toString("hex");
const sql = (q) => execFileSync("docker", ["exec", "pramaan-db", "psql", "-U", "pramaan", "-d", "pramaan", "-tAc", q], { encoding: "utf8" }).trim();
const mk = async (role) => {
  const email = `${role}-${tag}@example.com`;
  const r = await fetch(`${API}/v1/auth/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: "password123", name: role }) });
  assert.equal(r.status, 201);
  sql(`insert into user_roles (user_id, role_key, granted_at) select id, '${role}', now() from users where email='${email}'`);
  return email;
};
const auditor = await mk("auditor"), reviewer = await mk("reviewer");
const b = await chromium.launch();
const login = async (email) => {
  const page = await (await b.newContext({ viewport: { width: 1280, height: 900 }, bypassCSP: true })).newPage();
  page.setDefaultNavigationTimeout(90000);
  await page.goto(`${ADMIN}/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: "Review queue" }).waitFor({ timeout: 60000 });
  return page;
};
const step = async (n, fn) => { process.stdout.write(`• ${n} … `); await fn(); console.log("ok"); };

const a = await login(auditor);
await step("an auditor opens Calibration and it says plainly that it applies nothing", async () => {
  await a.getByRole("link", { name: "Calibration" }).click();
  await a.getByRole("heading", { name: "Calibration" }).waitFor();
  await a.getByRole("note").getByText(/applies nothing/).waitFor();
  await a.getByText("If the threshold had been lower").waitFor();
  assert.equal(await a.getByText("95%").first().isVisible(), true, "shows the current threshold");
  await a.screenshot({ path: "smoke-shots/calibration.png", fullPage: true });
});
const r = await login(reviewer);
await step("a reviewer is not offered the page, and the API refuses it", async () => {
  assert.equal(await r.getByRole("link", { name: "Calibration" }).count(), 0);
  await r.goto(`${ADMIN}/calibration`);
  await r.getByRole("alert").waitFor({ timeout: 30000 });
});
await b.close();
console.log("\nCalibration smoke test passed.");
