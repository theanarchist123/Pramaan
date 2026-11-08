// Phase 8: Hindi UI, PWA (manifest + service worker), resilience (offline banner, 404, offline page), accessibility (axe).
// Usage: node scripts/smoke-phase8.mjs [baseUrl] [outDir]     (needs a PRODUCTION build: the service worker only registers there)
import { chromium } from "playwright";
import { readFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const BASE = process.argv[2] ?? "http://localhost:3100";
const OUT = process.argv[3] ?? "smoke-shots";
mkdirSync(OUT, { recursive: true });
const axeSource = readFileSync(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");

const browser = await chromium.launch();
const errors = [];
const step = async (name, fn) => {
  process.stdout.write(`• ${name} … `);
  await fn();
  console.log("ok");
};
const watch = (page) => {
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => m.type() === "error" && !/404|Failed to load resource|ERR_/.test(m.text()) && errors.push(`console: ${m.text()}`));
};

const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, serviceWorkers: "allow" });
const page = await ctx.newPage();
watch(page);

await step("home renders in English, then switches to Hindi and remembers it", async () => {
  await page.goto(BASE);
  await page.getByRole("link", { name: "Directory" }).first().waitFor({ timeout: 20000 });
  assertLang(await page.evaluate(() => document.documentElement.lang), "en");
  await page.getByRole("button", { name: "Switch language" }).click();
  await page.getByRole("link", { name: "निर्देशिका" }).first().waitFor();
  assertLang(await page.evaluate(() => document.documentElement.lang), "hi");
  await page.screenshot({ path: `${OUT}/20-home-hindi.png` });
  await page.reload();
  await page.getByRole("link", { name: "निर्देशिका" }).first().waitFor();
  await page.getByRole("button", { name: "भाषा बदलें" }).click(); // back to English for the rest
  await page.getByRole("link", { name: "Directory" }).first().waitFor();
});

await step("Hindi carries through to the verify page", async () => {
  await page.getByRole("button", { name: "Switch language" }).click();
  await page.goto(`${BASE}/verify`);
  await page.getByRole("link", { name: "निर्देशिका" }).first().waitFor({ timeout: 20000 });
  const body = await page.textContent("body");
  if (!/[ऀ-ॿ]{4,}/.test(body ?? "")) throw new Error("no Devanagari text on /verify");
  await page.getByRole("button", { name: "भाषा बदलें" }).click();
});

await step("PWA manifest is valid and icons resolve", async () => {
  const res = await ctx.request.get(`${BASE}/manifest.webmanifest`);
  if (!res.ok()) throw new Error(`manifest ${res.status()}`);
  const m = await res.json();
  for (const k of ["name", "short_name", "start_url", "display", "icons"]) if (!m[k]) throw new Error(`manifest missing ${k}`);
  if (!m.icons.some((i) => (i.purpose ?? "").includes("maskable"))) throw new Error("no maskable icon");
  for (const i of m.icons) {
    const r = await ctx.request.get(new URL(i.src, BASE).href);
    if (!r.ok()) throw new Error(`icon ${i.src} → ${r.status()}`);
  }
});

await step("service worker registers and takes control", async () => {
  await page.goto(BASE);
  const ready = await page.evaluate(async () => {
    const reg = await Promise.race([navigator.serviceWorker.ready, new Promise((r) => setTimeout(() => r(null), 15000))]);
    return Boolean(reg && reg.active);
  });
  if (!ready) throw new Error("service worker never became active");
});

await step("the service worker never caches API calls", async () => {
  const sw = await ctx.request.get(`${BASE}/sw.js`);
  const src = await sw.text();
  if (!/\/v1\//.test(src) && !/api/i.test(src)) throw new Error("sw.js has no API bypass rule");
  const cached = await page.evaluate(async () => {
    const names = await caches.keys();
    const urls = [];
    for (const n of names) for (const r of await (await caches.open(n)).keys()) urls.push(r.url);
    return urls;
  });
  const bad = cached.filter((u) => /\/v1\/|:8000/.test(u));
  if (bad.length) throw new Error(`API responses were cached: ${bad.join(", ")}`);
});

await step("custom 404 page is friendly and links home", async () => {
  const r = await page.goto(`${BASE}/definitely-not-a-page`);
  if (r?.status() !== 404) throw new Error(`expected 404, got ${r?.status()}`);
  await page.getByRole("link", { name: /home|back/i }).first().waitFor();
  await page.screenshot({ path: `${OUT}/21-404.png` });
});

await step("going offline shows the connection banner; coming back clears it", async () => {
  await page.goto(BASE);
  await page.getByRole("link", { name: "Directory" }).first().waitFor();
  await ctx.setOffline(true);
  await page.getByRole("alert").or(page.getByRole("status")).filter({ hasText: /offline|connection|reach/i }).first().waitFor({ timeout: 15000 });
  await page.screenshot({ path: `${OUT}/22-offline-banner.png` });
  await ctx.setOffline(false);
  await page.getByText(/offline|can.?t reach|connection/i).first().waitFor({ state: "hidden", timeout: 30000 });
});

await step("offline navigation falls back to the bilingual offline page", async () => {
  await page.goto(BASE);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await ctx.setOffline(true);
  await page.goto(`${BASE}/some-uncached-route-${Date.now()}`).catch(() => {});
  await page.getByText(/offline|ऑफ़लाइन|इंटरनेट/i).first().waitFor({ timeout: 15000 });
  await page.screenshot({ path: `${OUT}/23-offline-page.png` });
  await ctx.setOffline(false);
});

// ------------------------------------------------------------------------------------------ accessibility
const AUDIT = ["/", "/verify", "/directory", "/developers", "/onboard", "/transparency", "/mission-control", "/auth"];
// Data-driven pages: find a real public profile (and its certificate) through the API, if there is one.
try {
  const API = process.env.API_URL ?? "http://localhost:8000";
  const hits = await (await fetch(`${API}/v1/search`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: "leader", limit: 8 }) })).json();
  for (const h of hits.results ?? []) {
    const certs = await (await fetch(`${API}/v1/public/${h.slug}/certificates`)).json();
    const code = Array.isArray(certs) ? certs[0]?.code : certs?.certificates?.[0]?.code;
    AUDIT.push(`/p/${h.slug}`);
    if (code) { AUDIT.push(`/verify/${code}`, `/certificate/${code}`); break; }
  }
} catch (e) {
  console.log(`(skipping data-driven pages: ${e.message})`);
}
// Signed-in pages (the seeded demo admin; skipped if it doesn't exist).
let adminToken = null;
try {
  const API = process.env.API_URL ?? "http://localhost:8000";
  const r = await fetch(`${API}/v1/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: "admin@pramaan.demo", password: "pramaan-demo-1" }) });
  if (r.ok) adminToken = (await r.json()).access_token;
} catch { /* no API */ }
if (adminToken) AUDIT.push("/me", "/admin", "/admin/builder", "/admin/outreach");
else console.log("(skipping signed-in pages: demo admin unavailable)");
const violations = [];
for (const scheme of ["light", "dark"]) {
  const c = await browser.newContext({ viewport: { width: 1360, height: 900 }, colorScheme: scheme, serviceWorkers: "block" });
  if (adminToken) await c.addInitScript((t) => { try { localStorage.setItem("pramaan.token", t); } catch {} }, adminToken);
  const p = await c.newPage();
  watch(p);
  for (const path of AUDIT) {
    await step(`axe (${scheme}) ${path}`, async () => {
      await p.goto(`${BASE}${path}`, { waitUntil: "networkidle" }).catch(() => p.goto(`${BASE}${path}`));
      await p.waitForTimeout(700); // let entrance animations settle so contrast is measured on final colours
      const dark = await p.evaluate(() => document.documentElement.classList.contains("dark"));
      if (dark !== (scheme === "dark")) throw new Error(`expected ${scheme} theme, <html class> says dark=${dark}`);
      await p.evaluate(axeSource);
      const res = await p.evaluate(() => window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] } }));
      for (const v of res.violations) {
        violations.push({ scheme, path, id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.slice(0, 3).map((n) => `${n.target.join(" ")} :: ${(n.any[0]?.message ?? n.failureSummary ?? "").split("\n")[0]}`) });
      }
    });
  }
  await c.close();
}

function assertLang(actual, expected) {
  if (actual !== expected) throw new Error(`<html lang> is "${actual}", expected "${expected}"`);
}

await browser.close();

const serious = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
console.log(`\naxe: ${violations.length} violation(s), ${serious.length} serious/critical`);
const seen = new Set();
for (const v of violations) {
  const key = `${v.id}|${v.nodes[0]}`;
  if (seen.has(key)) continue;
  seen.add(key);
  console.log(`  [${v.impact}] ${v.id} — ${v.help}  (${v.scheme} ${v.path})`);
  for (const n of v.nodes) console.log(`      ${n}`);
}
if (errors.length) console.log(`\nbrowser errors:\n  ${[...new Set(errors)].join("\n  ")}`);
process.exit(serious.length || errors.length ? 1 : 0);
