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
page.on("console", (m) => m.type() === "error" && !m.text().includes("404") && !m.text().includes("caret-color") /* Playwright adds this style to inputs when it takes a screenshot */ && !m.text().includes("401") /* a signed-out visitor always gets 401 from the "who am I" probe */ && errors.push(`console: ${m.text()}`));
const step = async (name, fn) => { process.stdout.write(`• ${name} … `); await fn(); console.log("ok"); };

await step("directory lists the demo registry", async () => {
  // The page lists the newest 100 people; a database with many other profiles can push the seeded demo people out of that window, so ask for her by name.
  await page.goto(`${BASE}/directory?q=${encodeURIComponent("Ananya Rekhi")}`);
  await page.getByText("Ananya Rekhi").first().waitFor({ timeout: 60000 });
  await page.goto(`${BASE}/directory`);
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
  await page.goto(`${BASE}/directory?q=${encodeURIComponent("Ananya Rekhi")}`);
  // the person's link, not the first text that says her name (while searching, the page also says "Searching for Ananya Rekhi")
  await page.getByRole("link", { name: /Ananya Rekhi/ }).first().click();
  await page.waitForURL(/\/p\/demo-/);
  // the registry's wording is "confirmed" (a public-source claim is never counted as verified): smoke-pages checks the negative
  await page.locator("#main").getByText(/claims confirmed/).waitFor();
  await page.getByText("Show the evidence").first().click();
  await page.getByText("Fictional demo profile").waitFor();
  await page.screenshot({ path: `${OUT}/14-profile.png`, fullPage: true });
});

// v3: the web app's own /admin pages were retired. Staff work lives in the Desk, served from the same address under /staff
// (its own sign-in is covered by apps/admin/scripts/smoke.mjs), so the old address must lead there instead of showing a queue.
await step("the old /admin address leads to the staff Desk on the same port", async () => {
  await page.goto(`${BASE}/admin`);
  await page.waitForURL(/\/staff/, { timeout: 20000 });
  await page.getByRole("heading", { name: /The Desk\./ }).waitFor({ timeout: 30000 });
  await page.screenshot({ path: `${OUT}/15-admin.png` });
});

await browser.close();
if (errors.length) { console.log("\nBrowser errors:\n" + errors.join("\n")); process.exitCode = 1; } else console.log("\nNo browser errors.");
