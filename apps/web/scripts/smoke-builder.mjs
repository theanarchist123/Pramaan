// Phase 7 end to end, as a real admin in a real browser: Shilpkar adds a field (instantly live),
// writes a plugin (guard → Docker sandbox → approval → live endpoint), and Doot drafts + sends outreach.
// Usage: node scripts/smoke-builder.mjs [baseUrl] [apiUrl] [outDir]     (needs seeded demo admin + Docker image)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.argv[2] ?? "http://localhost:3100";
const API = process.argv[3] ?? "http://localhost:8000";
const OUT = process.argv[4] ?? "smoke-shots";
mkdirSync(OUT, { recursive: true });
const json = { "Content-Type": "application/json" };
const j = async (r) => { if (!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json(); };

const admin = await j(await fetch(`${API}/v1/auth/login`, { method: "POST", headers: json, body: JSON.stringify({ email: "admin@pramaan.demo", password: "pramaan-demo-1" }) }));
const A = { ...json, Authorization: `Bearer ${admin.access_token}` };

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1000 } });
await ctx.addInitScript((t) => localStorage.setItem("pramaan.token", t), admin.access_token);
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => m.type() === "error" && !m.text().includes("404") && errors.push(`console: ${m.text()}`));
const step = async (name, fn) => { process.stdout.write(`• ${name} … `); await fn(); console.log("ok"); };
const stamp = Date.now().toString(36).replace(/\d/g, (d) => "abcdefghij"[d]); // letters only, so it can't hint at a field type

await step("Shilpkar drafts a field from a sentence; nothing exists until approved", async () => {
  await page.goto(`${BASE}/admin/builder`);
  await page.getByRole("heading", { name: "Builder" }).waitFor();
  await page.getByLabel("Describe the field you want").fill(`add a patents held ${stamp} field`);
  await page.getByRole("button", { name: "Draft it" }).click();
  await page.getByText("nothing exists until you approve").waitFor({ timeout: 30000 });
  const before = await j(await fetch(`${API}/v1/fields`));
  if (before.some((f) => f.key.includes(stamp))) throw new Error("field existed before approval");
  await page.screenshot({ path: `${OUT}/30-builder-field-draft.png` });
  await page.getByRole("button", { name: "Approve & create" }).click();
  await page.getByText(/is live — forms, profiles, search/).waitFor();
});

await step("the new field is live everywhere with no deploy", async () => {
  const defs = await j(await fetch(`${API}/v1/fields`));
  const f = defs.find((x) => x.key.startsWith("patents_held"));
  if (!f) throw new Error("not in the public field list");
  // a brand-new person sees it in their onboarding panel, and the API accepts a value for it
  const email = `bld-${Date.now()}@example.com`;
  const reg = await j(await fetch(`${API}/v1/auth/register`, { method: "POST", headers: json, body: JSON.stringify({ email, password: "password123", name: "Field Tester" }) }));
  const P = { ...json, Authorization: `Bearer ${reg.access_token}` };
  const started = await j(await fetch(`${API}/v1/onboarding/start`, { method: "POST", headers: P, body: JSON.stringify({ consent_public_listing: true }) }));
  const sample = { list: ["US-123", "US-456"], text: "US-123, US-456", number: 7, url: "https://example.org/patents", date: "2020-01-01" };
  const bad = await fetch(`${API}/v1/profiles/${started.profile.id}`, { method: "PATCH", headers: P, body: JSON.stringify({ custom: { [f.key]: sample[f.type] } }) });
  if (!bad.ok) throw new Error(`value rejected: ${await bad.text()}`);
  const ctx2 = await browser.newContext({ viewport: { width: 1360, height: 900 } });
  await ctx2.addInitScript((t) => localStorage.setItem("pramaan.token", t), reg.access_token);
  const p2 = await ctx2.newPage();
  await p2.goto(`${BASE}/onboard`);
  await p2.getByText("Patents held").first().waitFor({ timeout: 20000 });
  await p2.getByText(f.type === "number" ? "7" : f.type === "url" ? "https://example.org/patents" : "US-123, US-456", { exact: true }).first().waitFor();
  await p2.screenshot({ path: `${OUT}/31-field-in-onboarding.png` });
  await ctx2.close();
});

let slug = "";
await step("Shilpkar writes a plugin: guard + sandbox pass, you read the code", async () => {
  await page.goto(`${BASE}/admin/builder`);
  await page.getByLabel("Describe the plugin you want").fill(`make an endpoint showing the number of members in each state. Name the plugin ps_${stamp}`);
  await page.getByRole("button", { name: "Build it" }).click();
  await page.getByText("Ready for your approval").first().waitFor({ timeout: 120000 });
  await page.getByText("Code guard passed").first().waitFor();
  await page.getByText("tests (pytest)").first().waitFor();
  await page.getByRole("button", { name: /Read the code/ }).first().click();
  await page.getByText("router = APIRouter").first().waitFor();
  slug = (await page.locator("p.font-mono", { hasText: /^plugins\/(?!test_)/ }).first().textContent()).replace("plugins/", "").replace(".py", "");
  await page.screenshot({ path: `${OUT}/32-builder-plugin-ready.png`, fullPage: true });
});

await step("approve → the endpoint goes live without a restart", async () => {
  const before = await fetch(`${API}/v1/plugins/${slug}`);
  if (before.status !== 404) throw new Error(`plugin was live before approval (${before.status})`);
  await page.getByRole("button", { name: "Approve & go live" }).first().click();
  await page.getByText(/is live at \/v1\/plugins\//).waitFor({ timeout: 20000 });
  const live = await j(await fetch(`${API}/v1/plugins/${slug}`));
  // The shape is whatever the author (a live model, or the offline stand-in) chose — require real content.
  if (!JSON.stringify(live).match(/Maharashtra|Karnataka|Kerala/)) throw new Error(`plugin returned no member data: ${JSON.stringify(live).slice(0, 120)}`);
  await page.screenshot({ path: `${OUT}/33-builder-plugin-live.png`, fullPage: true });
});

await step("Doot drafts a nudge; an admin edits and approves it; nothing was auto-sent", async () => {
  const email = `out-${Date.now()}@example.com`;
  const reg = await j(await fetch(`${API}/v1/auth/register`, { method: "POST", headers: json, body: JSON.stringify({ email, password: "password123", name: "Asha Nudge" }) }));
  const P = { ...json, Authorization: `Bearer ${reg.access_token}` };
  const pr = await j(await fetch(`${API}/v1/profiles`, { method: "POST", headers: P, body: JSON.stringify({ full_name: "Asha Nudge", consent_public_listing: true }) }));
  await j(await fetch(`${API}/v1/profiles/${pr.id}/claims`, { method: "POST", headers: P, body: JSON.stringify({ field: "award", value: "Some award", year: 2024 }) }));
  await j(await fetch(`${API}/v1/admin/outreach/suggest`, { method: "POST", headers: A, body: JSON.stringify({ idle_after_hours: 0 }) }));

  await page.goto(`${BASE}/admin/outreach`);
  await page.getByText(email).waitFor({ timeout: 20000 });
  const card = page.locator("li", { hasText: email });
  await card.getByText("Finish your profile").waitFor();
  await page.screenshot({ path: `${OUT}/34-outreach-draft.png`, fullPage: true });
  const out = await j(await fetch(`${API}/v1/admin/outbox?status=sent`, { headers: A }));
  if (out.some((m) => m.to_email === email)) throw new Error("a draft was sent without approval");

  await card.getByLabel("Subject").fill("A note from the Pramaan team (edited by a human)");
  await card.getByRole("button", { name: "Send now" }).click();
  await page.getByText(/Recorded as sent \(dry run/).waitFor();
  await page.getByRole("tab", { name: /^sent/ }).click();
  await page.locator("li", { hasText: email }).getByText("A note from the Pramaan team (edited by a human)").waitFor();
  await page.screenshot({ path: `${OUT}/35-outreach-sent.png` });
});

await browser.close();
console.log(JSON.stringify({ slug }));
if (errors.length) { console.log("\nBrowser errors:\n" + errors.join("\n")); process.exitCode = 1; } else console.log("\nNo browser errors.");
