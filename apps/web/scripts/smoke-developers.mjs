// Developer portal, end to end — including a REAL webhook delivery verified with the TypeScript SDK.
// Usage: node scripts/smoke-developers.mjs [baseUrl] [apiUrl] [outDir]
import { chromium } from "playwright";
import { createServer } from "node:http";
import { mkdirSync } from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";

const BASE = process.argv[2] ?? "http://localhost:3100";
const API = process.argv[3] ?? "http://localhost:8000";
const OUT = process.argv[4] ?? "smoke-shots";
mkdirSync(OUT, { recursive: true });
const sdk = await import(pathToFileURL(path.resolve("../../packages/sdk/typescript/dist/index.js")).href);

// A stand-in for a developer's server: records what Pramaan POSTs to it.
const received = [];
const receiver = createServer((req, res) => {
  const chunks = [];
  req.on("data", (c) => chunks.push(c));
  req.on("end", () => {
    received.push({ headers: req.headers, body: Buffer.concat(chunks).toString("utf-8") });
    res.writeHead(200).end("ok");
  });
}).listen(9099);

// Register a developer account directly through the API, then give the browser its session.
const email = `dev-${Date.now()}@example.com`;
const reg = await (await fetch(`${API}/v1/auth/register`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password: "password123", name: "Dev Tester" }),
})).json();

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
await ctx.addInitScript((t) => localStorage.setItem("pramaan.token", t), reg.access_token);
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => m.type() === "error" && !m.text().includes("404") && errors.push(`console: ${m.text()}`));
const step = async (name, fn) => { process.stdout.write(`• ${name} … `); await fn(); console.log("ok"); };

await step("quickstart shows code for each language", async () => {
  await page.goto(`${BASE}/developers`);
  await page.getByRole("heading", { name: "Build on Pramaan" }).waitFor();
  await page.getByText("curl ").first().waitFor();
  await page.getByRole("tab", { name: "Python" }).click();
  await page.getByText("check_payload").first().waitFor();
  await page.getByRole("tab", { name: "MCP (AI agents)" }).click();
  await page.getByText("search_registry").first().waitFor();
  await page.screenshot({ path: `${OUT}/20-dev-quickstart.png` });
});

await step("playground: send a real request", async () => {
  await page.getByRole("tab", { name: "Playground" }).click();
  await page.getByRole("button", { name: "Send request" }).click();
  await page.getByText('"signature_ok": true').waitFor({ timeout: 20000 });
  await page.screenshot({ path: `${OUT}/21-dev-playground.png` });
});

await step("API keys: create (shown once) and revoke", async () => {
  await page.getByRole("tab", { name: "API keys" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Smoke key");
  await page.getByRole("button", { name: "Create key" }).click();
  await page.getByText("it won't be shown again").waitFor();
  const key = await page.locator("code", { hasText: /^pk_live_/ }).first().textContent();
  if (!key?.startsWith("pk_live_")) throw new Error("no key shown");
  const who = await fetch(`${API}/v1/profiles/mine`, { headers: { "X-API-Key": key } });
  if (who.status !== 200) throw new Error(`new key rejected: ${who.status}`);
  await page.screenshot({ path: `${OUT}/22-dev-keys.png` });
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Revoke Smoke key" }).click();
  await page.getByText("revoked", { exact: true }).waitFor();
  const after = await fetch(`${API}/v1/profiles/mine`, { headers: { "X-API-Key": key } });
  if (after.status !== 401) throw new Error(`revoked key still works: ${after.status}`);
});

let secret = "";
await step("webhooks: create, test event arrives and its signature verifies", async () => {
  await page.getByRole("tab", { name: "Webhooks" }).click();
  await page.getByLabel("Endpoint URL (https)").fill("http://localhost:9099/hook");
  await page.getByRole("button", { name: "Create webhook" }).click();
  await page.getByText("Signing secret — shown only once").waitFor();
  secret = (await page.locator("code", { hasText: /^whsec_/ }).first().textContent()) ?? "";
  await page.getByRole("button", { name: "Send a test event" }).click();
  await page.getByText(/Your endpoint answered 200/).waitFor({ timeout: 20000 });
  if (!received.length) throw new Error("receiver got nothing");
  const { headers, body } = received[0];
  if (!(await sdk.verifyWebhook(secret, headers["x-pramaan-signature"], body))) throw new Error("signature did not verify");
  if (JSON.parse(body).event !== "ping") throw new Error("wrong event");
  if (await sdk.verifyWebhook("whsec_wrong", headers["x-pramaan-signature"], body)) throw new Error("accepted the wrong secret");
  await page.getByText("Show deliveries").click();
  await page.getByText(/attempt 1/).waitFor();
  await page.screenshot({ path: `${OUT}/23-dev-webhooks.png` });
});

await step("badge generator renders a live badge", async () => {
  await page.getByRole("tab", { name: "Badges" }).click();
  const img = page.locator("img[alt^='Verified by Pramaan']");
  await img.waitFor();
  await page.waitForFunction(() => { const i = document.querySelector("img[alt^='Verified by Pramaan']"); return i && i.complete && i.naturalWidth > 0; }, null, { timeout: 15000 });
  await page.screenshot({ path: `${OUT}/24-dev-badge.png` });
});

await browser.close();
receiver.close();
if (errors.length) { console.log("\nBrowser errors:\n" + errors.join("\n")); process.exitCode = 1; } else console.log("\nNo browser errors.");
