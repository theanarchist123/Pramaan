// Directory flow: semantic search, network, India map, public profile, admin review.
// Usage: node scripts/smoke-directory.mjs [baseUrl] [outDir]   (needs seeded demo data)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.argv[2] ?? "http://localhost:3100";
const OUT = process.argv[3] ?? "smoke-shots";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => m.type() === "error" && !m.text().includes("404") && errors.push(`console: ${m.text()}`));
const step = async (name, fn) => { process.stdout.write(`• ${name} … `); await fn(); console.log("ok"); };

await step("directory lists the demo registry", async () => {
  await page.goto(`${BASE}/directory`);
  await page.getByText("Ananya Rekhi").first().waitFor({ timeout: 20000 });
  await page.screenshot({ path: `${OUT}/10-directory.png` });
});

await step("plain-English question → ranked people with reasons", async () => {
  await page.getByRole("button", { name: /clean-energy innovators in Karnataka/ }).click();
  await page.getByText("Why this person").first().waitFor({ timeout: 60000 });
  await page.getByText(/Understood your question/).waitFor();
  await page.screenshot({ path: `${OUT}/11-search.png` });
});

await step("network view draws the constellation", async () => {
  await page.getByRole("tab", { name: "Network" }).click();
  await page.locator("canvas").first().waitFor();
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${OUT}/12-network.png` });
});

await step("India map: states render and clicking filters", async () => {
  await page.getByRole("tab", { name: "Map" }).click();
  await page.waitForFunction(() => document.querySelectorAll("svg path[role=button]").length > 30, null, { timeout: 15000 });
  await page.getByRole("button", { name: /^Karnataka: \d+ members?/ }).click();
  await page.getByText("Karnataka", { exact: true }).first().waitFor();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/13-map.png` });
});

await step("public profile page shows verified claims with evidence", async () => {
  await page.goto(`${BASE}/directory`);
  await page.getByText("Ananya Rekhi").first().click();
  await page.waitForURL(/\/p\/demo-/);
  await page.getByText(/claims verified/).waitFor();
  await page.getByText("Show the evidence").first().click();
  await page.getByText("Fictional demo profile").waitFor();
  await page.screenshot({ path: `${OUT}/14-profile.png`, fullPage: true });
});

await step("admin signs in and reviews the queue", async () => {
  await page.goto(`${BASE}/auth?next=/admin`);
  await page.getByRole("button", { name: /Already have an account/ }).click();
  await page.getByLabel("Email").fill("admin@pramaan.demo");
  await page.getByLabel("Password").fill("pramaan-demo-1");
  await page.getByRole("button", { name: "Sign in" }).last().click();
  await page.waitForURL(/\/admin/);
  await page.getByRole("heading", { name: "Review queue" }).waitFor();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/15-admin.png`, fullPage: true });
  const approve = page.getByRole("button", { name: /Approve & publish/ }).first();
  if (await approve.count()) {
    await approve.click();
    await page.getByText(/approved and added to the directory/).waitFor({ timeout: 15000 });
  }
});

await browser.close();
if (errors.length) { console.log("\nBrowser errors:\n" + errors.join("\n")); process.exitCode = 1; } else console.log("\nNo browser errors.");
