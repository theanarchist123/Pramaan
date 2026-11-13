// Browser test of two pages that no other script covers: the published view page (/v/[slug], tier T2) and the OAuth consent screen (/oauth/authorize).
// Needs a RUNNING API + web app and the LOCAL docker database.   node scripts/smoke-newpages.mjs [webUrl] [apiUrl]
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import assert from "node:assert/strict";

const WEB = process.argv[2] ?? "http://localhost:3013";
const API = process.argv[3] ?? "http://localhost:8010";
const sql = (q) => execFileSync("docker", ["exec", "pramaan-db", "psql", "-U", "pramaan", "-d", "pramaan", "-tAc", q], { encoding: "utf8" }).trim();
const J = { "Content-Type": "application/json" };
const call = (path, token, body, method = "POST") => fetch(`${API}${path}`, { method, headers: { ...J, ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: body ? JSON.stringify(body) : undefined });
const tag = randomBytes(3).toString("hex");
const reg = async (email) => (await (await call("/v1/auth/register", null, { email, password: "password123", name: "Smoke" })).json()).access_token;

const browser = await chromium.launch();
const errors = [];
const step = async (n, fn) => { process.stdout.write(`• ${n} … `); await fn(); console.log("ok"); };

await step("VIEW PAGE: a published view draws its stat and bars from the public API, and a draft is not found", async () => {
  const a = `view-a-${tag}@example.com`, b = `view-b-${tag}@example.com`;
  const ta = await reg(a), tb = await reg(b);
  sql(`update users set role='admin' where email in ('${a}','${b}')`);
  const made = await (await call("/v1/admin/views", ta, { request: "show members per state please" })).json();
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  page.setDefaultNavigationTimeout(90000);
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${WEB}/v/${made.slug}`);
  await page.getByRole("heading", { name: "Page not found" }).waitFor(); // a draft is public to no one
  assert.equal((await call(`/v1/admin/views/${made.id}/publish`, ta)).status, 403); // not by its own author
  assert.equal((await call(`/v1/admin/views/${made.id}/publish`, tb)).status, 200);
  await page.goto(`${WEB}/v/${made.slug}`);
  await page.getByRole("heading", { name: "Members per state" }).waitFor();
  await page.getByText("Total members").waitFor();
  await page.getByText("By state").waitFor();
  assert.equal(await page.locator("script:not([src])").evaluateAll((s) => s.filter((x) => /alert\(|eval\(/.test(x.textContent || "")).length), 0);
});

await step("CONSENT SCREEN: shows the app and what it can do, Allow sends a code to the registered address only, Deny sends access_denied", async () => {
  const email = `oauth-${tag}@example.com`;
  const token = await reg(email);
  const redirect = "https://app.example.org/callback";
  const client = await (await call("/v1/oauth/clients", token, { name: "Demo reader", redirect_uris: [redirect] })).json();
  const verifier = randomBytes(40).toString("base64url");
  const challenge = createHash("sha256").update(verifier).digest("base64url");
  const q = new URLSearchParams({ client_id: client.client_id, redirect_uri: redirect, scope: "verify:read profiles:read", state: "s1", code_challenge: challenge, code_challenge_method: "S256", response_type: "code" });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  page.setDefaultNavigationTimeout(90000);
  page.on("pageerror", (e) => errors.push(e.message));
  const landed = [];
  await ctx.route("https://app.example.org/**", (route) => { landed.push(route.request().url()); return route.fulfill({ status: 200, body: "callback reached" }); });
  await page.goto(`${WEB}/auth?mode=login&next=${encodeURIComponent(`/oauth/authorize?${q}`)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: "Let an app in?" }).waitFor();
  await page.getByText("Demo reader").first().waitFor();
  await page.getByText("Check whether certificates are genuine").waitFor();
  await page.getByText("Read your own profiles").waitFor();
  assert.equal(await page.getByText("Create and change your profiles").count(), 0); // only what was asked for
  await page.getByRole("button", { name: "Allow", exact: true }).click();
  await page.waitForURL((u) => u.hostname === "app.example.org");
  const url = new URL(page.url());
  assert.equal(url.origin + url.pathname, redirect);
  assert.ok(url.searchParams.get("code") && url.searchParams.get("state") === "s1");
  // a hostile redirect is an error on the page, never a redirect
  const bad = new URLSearchParams(q); bad.set("redirect_uri", "https://evil.example/cb");
  await page.goto(`${WEB}/oauth/authorize?${bad}`);
  await page.getByRole("alert").waitFor();
  assert.equal(new URL(page.url()).hostname, new URL(WEB).hostname); // still on our site (the address text itself is in the query string)
  // deny
  await page.goto(`${WEB}/oauth/authorize?${q}`);
  await page.getByRole("button", { name: "Don't allow" }).click();
  await page.waitForURL((u) => u.hostname === "app.example.org");
  assert.equal(new URL(page.url()).searchParams.get("error"), "access_denied");
});

await step("SIGN-IN: a crafted ?next= pointing off-site is ignored", async () => {
  const email = `next-${tag}@example.com`;
  await reg(email);
  const page = await (await browser.newContext()).newPage();
  page.setDefaultNavigationTimeout(90000);
  await page.goto(`${WEB}/auth?mode=login&next=${encodeURIComponent("https://evil.example/x")}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((u) => u.origin === new URL(WEB).origin && !u.pathname.startsWith("/auth"));
  assert.equal(new URL(page.url()).hostname, new URL(WEB).hostname);
});

await browser.close();
assert.deepEqual(errors, []);
console.log("\nNew pages smoke test passed.");
