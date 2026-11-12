// Browser test of the photograph curation page against a RUNNING API + admin app. With no UNSPLASH_ACCESS_KEY the search must fail with a
// clear, actionable message (not a crash), the page must list all 14 fields, and the approved list must start empty.
//   node scripts/smoke-images.mjs [adminUrl] [apiUrl]
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import assert from "node:assert/strict";
const ADMIN = process.argv[2] ?? "http://localhost:3011", API = process.argv[3] ?? "http://localhost:8010";
const tag = randomBytes(3).toString("hex"), email = `img-${tag}@example.com`;
const sql = (q) => execFileSync("docker", ["exec", "pramaan-db", "psql", "-U", "pramaan", "-d", "pramaan", "-tAc", q], { encoding: "utf8" }).trim();
const r = await fetch(`${API}/v1/auth/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: "password123", name: "Image Curator" }) });
assert.equal(r.status, 201);
sql(`update users set role='admin' where email='${email}'`);
const b = await chromium.launch();
const page = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
page.setDefaultNavigationTimeout(90000);
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const step = async (n, fn) => { process.stdout.write(`• ${n} … `); await fn(); console.log("ok"); };
await step("sign in and open Photographs from the console", async () => {
  await page.goto(`${ADMIN}/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("link", { name: "Photographs" }).click();
  await page.getByRole("heading", { name: "Photographs" }).waitFor();
});
await step("all 14 fields are offered, and nothing is approved yet", async () => {
  assert.equal(await page.getByLabel("Approve into").locator("option").count(), 14);
  await page.getByText(/None yet\./).waitFor();
});
await step("searching without a key says exactly what to do, and does not crash", async () => {
  await page.getByLabel("Search Unsplash").fill("wind turbines");
  await page.getByRole("button", { name: "Search" }).click();
  await page.getByRole("alert").getByText(/UNSPLASH_ACCESS_KEY/).waitFor();
});
await b.close();
assert.deepEqual(errors, []);
console.log("\nPhotograph curation smoke test passed.");
