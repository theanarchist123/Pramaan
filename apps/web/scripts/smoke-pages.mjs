// Browser smoke test of the Phase 1 pages other than Verify: Home, Directory, Profile, Transparency, Developers, Agent Floor.
// Needs a RUNNING API + web app and the local docker database.  node scripts/smoke-pages.mjs [webUrl] [apiUrl]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import assert from "node:assert/strict";

const WEB = process.argv[2] ?? "http://localhost:3012";
const API = process.argv[3] ?? "http://localhost:8010";
mkdirSync("smoke-shots", { recursive: true });

const browser = await chromium.launch();
const errors = [];
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, bypassCSP: true }); // only lets Playwright run its own checks; the app CSP is unchanged
const page = await ctx.newPage();
page.setDefaultNavigationTimeout(90000); // a dev server compiles each route on first use
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error" && !/404|Failed to load resource/.test(m.text())) errors.push(`console: ${m.text().slice(0, 300)}`); });
const step = async (name, fn) => { process.stdout.write(`• ${name} … `); await fn(); console.log("ok"); };
const shot = (n) => page.screenshot({ caret: "initial", path: `smoke-shots/${n}.png`, fullPage: true });

const people = await (await fetch(`${API}/v1/profiles?limit=100`)).json();
const slug = people[0]?.slug;
// ---- seed one profile whose biography repeats a reviewer-CONFIRMED claim word for word, plus a sentence that matches nothing -------------------
const tag = randomBytes(3).toString("hex");
const sql = (q) => execFileSync("docker", ["exec", "pramaan-db", "psql", "-U", "pramaan", "-d", "pramaan", "-tAc", q], { encoding: "utf8" }).trim();
const J = { "Content-Type": "application/json" };
const post = (path, token, body, method = "POST") => fetch(`${API}${path}`, { method, headers: { ...J, ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: body ? JSON.stringify(body) : undefined });
const reg = async (email) => (await (await post("/v1/auth/register", null, { email, password: "password123", name: "Seed" })).json()).access_token;
const CLAIM = "Sagar Samman for marine research";
const adminTok = await reg(`bp-a-${tag}@example.com`);
sql(`update users set role='admin' where email='bp-a-${tag}@example.com'`);
const memberTok = await reg(`bp-m-${tag}@example.com`);
sql(`update users set email_verified_at = now() where email='bp-m-${tag}@example.com'`);
const bioProfile = await (await post("/v1/profiles", memberTok, { full_name: `Bio Proof ${tag}`, sector: "Science", state: "Kerala", consent_public_listing: true })).json();
await post(`/v1/profiles/${bioProfile.id}`, memberTok, { bio: `She won the ${CLAIM} in 2024. She also enjoys long walks by the sea.` }, "PATCH");
const bioClaim = await (await post(`/v1/profiles/${bioProfile.id}/claims`, memberTok, { field: "award", value: CLAIM })).json();
await post(`/v1/profiles/${bioProfile.id}/submit`, memberTok);
await post(`/v1/admin/claims/${bioClaim.id}/verify`, adminTok, { reason: "Checked against the published honours list", evidence_ref: "https://example.org/honours" });
await post(`/v1/admin/profiles/${bioProfile.id}/status`, adminTok, { status: "approved" });

// ---- seed one REAL verification run on a fictional demo profile, for the public replay ---------------------------------------------------
const demoTok = await reg(`dm-${tag}@example.com`);
sql(`update users set email_verified_at = now() where email='dm-${tag}@example.com'`);
const demoStart = await (await post("/v1/onboarding/start", demoTok, { full_name: `Demo Replay ${tag}`, consent_public_listing: true, consent_web_research: false })).json();
await post(`/v1/onboarding/${demoStart.profile.id}/message`, demoTok, { text: "I am a marine scientist working in Kerala. I received the Sagar Samman award in 2024." });
sql(`update profiles set is_demo = true where id='${demoStart.profile.id}'`);
await post(`/v1/onboarding/${demoStart.profile.id}/verify`, demoTok);


await step("HOME: hero proof table checks a real certificate (or says there is none), ledger strip, no mock screenshot", async () => {
  await page.goto(`${WEB}/`);
  await page.getByText("Checked just now").waitFor();
  await page.getByText(/Confirmed it has not been revoked|has been revoked|There is no certificate to check yet/).waitFor({ timeout: 8000 });
  assert.equal(await page.getByText("Example profile · sample data").count(), 0);
  // the desk certificate: change a letter and the REGISTRY says the signature no longer holds
  const box = page.getByLabel(/Try to forge it/);
  await box.waitFor({ timeout: 20000 });
  await page.getByText("Signature valid: this is the real name").waitFor();
  const original = await box.inputValue();
  await box.fill(original.slice(0, -1) + (original.endsWith("x") ? "y" : "x"));
  await page.getByText("Signature broken: the registry refuses it").waitFor({ timeout: 10000 });
  await page.getByText("NOT VALID").waitFor();
  await box.fill(original);
  await page.getByText("Signature valid: this is the real name").waitFor({ timeout: 10000 });
  // browse by field: 14 tiles, each linking to the filtered directory
  const tiles = page.getByRole("link", { name: /: \d+ (person|people)$/ });
  assert.equal(await tiles.count(), 14, "one tile per field");
  await tiles.first().click();
  await page.waitForURL(/\/directory\?sector=/);
  await page.getByRole("button", { name: /^(Science|Technology|Energy|Healthcare)/, pressed: true }).first().waitFor({ timeout: 15000 });
  await page.goto(`${WEB}/`);
  await shot("home");
});
await step("UNSPLASH SLOTS: an approved photo is hotlinked (never self-hosted), sized by the CDN, duotoned, and credited with linked, tagged attribution", async () => {
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64");
  const requested = [];
  const fake = [{ id: "test-fixture", sector: "Science", purpose: "tile", url_raw: "https://images.unsplash.com/test-fixture?ixid=TEST", width: 1000, height: 700, blur_hash: "", dominant_color: "#336699", alt: "A test fixture, not a real photograph",
    attribution: { photographer: "Test Photographer", photographer_url: "https://unsplash.com/@test?utm_source=pramaan&utm_medium=referral", photo_url: "https://unsplash.com/photos/test?utm_source=pramaan&utm_medium=referral", unsplash_url: "https://unsplash.com/?utm_source=pramaan&utm_medium=referral" } }];
  await page.route("**/v1/images/sector/**", (r) => r.fulfill({ json: fake }));
  await page.route("https://images.unsplash.com/**", (r) => { requested.push(r.request().url()); return r.fulfill({ body: png, contentType: "image/png" }); });
  await page.goto(`${WEB}/`);
  const credit = page.getByText("Test Photographer").first();
  await credit.waitFor({ timeout: 20000 });
  const hrefs = await page.locator("figcaption a").evaluateAll((a) => a.map((x) => x.getAttribute("href")));
  assert.ok(hrefs.length >= 2 && hrefs.every((h) => /utm_source=pramaan/.test(h)), "both credit links carry the utm tags");
  await page.waitForFunction(() => document.querySelectorAll("figure img").length > 0);
  const src = await page.locator("figure img").first().getAttribute("src");
  assert.match(src, /^https:\/\/images\.unsplash\.com\//, "hotlinked from Unsplash");
  assert.match(src, /ixid=TEST/, "the ixid (view tracking) is kept");
  assert.match(src, /w=\d+&q=70&fm=webp/, "sized with the image CDN parameters");
  assert.ok(requested.length > 0, "the browser, not our server, fetched the photo");
  await shot("home-with-photo");
  await page.unroute("**/v1/images/sector/**");
  await page.unroute("https://images.unsplash.com/**");
});
await step("DIRECTORY: shelves per field when unfiltered, a filter switches to one grid", async () => {
  await page.goto(`${WEB}/directory`);
  await page.getByRole("heading", { level: 1 }).waitFor();
  const shelf = page.locator("section[aria-label*=' person'], section[aria-label*=' people']");
  if (people.length >= 6) await shelf.first().waitFor({ timeout: 10000 });
  if (people.length >= 6) {
    // each shelf has a cover band naming the field, and a sideways-scrolling row of people
    await page.getByRole("list", { name: /people, scroll sideways$/ }).first().waitFor();
    // search mode: a real question gives a ranked list where every result says why
    const box = page.getByRole("textbox", { name: /search/i }).first();
    await box.fill("marine scientist in Kerala");
    await box.press("Enter"); // the header also has a Search button, so submit the form itself
    const ranked = page.getByRole("list", { name: "Results, best match first" });
    await ranked.waitFor({ timeout: 20000 });
    const rows = ranked.locator(":scope > li"); // top-level results only (each also holds its own reason bullets)
    assert.ok((await rows.count()) >= 1, "at least one ranked result");
    assert.equal(await ranked.getByLabel("Rank 1", { exact: true }).count(), 1, "the first result is ranked 1");
    const explained = await rows.evaluateAll((els) => els.filter((e) => /Why this person|Confirmed|Public evidence|Document|Self-claimed/.test(e.textContent)).length);
    assert.equal(explained, await rows.count(), "every result explains itself");
    await shot("directory-search");
    await page.goto(`${WEB}/directory`);
  }
  else await page.getByRole("link", { name: /./ }).first().waitFor();
  await shot("directory");
});
if (slug) {
  await step("PROFILE: claim counts say 'confirmed', never count a public-source claim as verified; evidence slip opens", async () => {
    await page.goto(`${WEB}/p/${slug}`);
    await page.getByText(/of \d+ claims confirmed/).waitFor();
    assert.equal(await page.getByText(/claims verified/).count(), 0);
    const btn = page.getByRole("button", { name: "Show the evidence" }).first();
    if (await btn.count()) { await btn.click(); await page.getByRole("button", { name: "Hide the evidence" }).first().waitFor(); }
    await shot("profile");
  });
}
await step("PROFILE BIO PROOF: 'Show what's proven' marks only the sentence that repeats a confirmed claim word for word", async () => {
  await page.goto(`${WEB}/p/${bioProfile.slug}`);
  const toggle = page.getByRole("button", { name: /Show what.s proven/ });
  await toggle.waitFor({ timeout: 20000 });
  assert.equal(await page.locator("p span.bg-verified-soft").count(), 0, "nothing is marked until asked");
  await toggle.click();
  await page.getByRole("status").filter({ hasText: /1 sentence repeats a confirmed claim word for word/ }).waitFor();
  const marked = await page.locator("p span.bg-verified-soft").allTextContents();
  assert.equal(marked.length, 1, "exactly one sentence is marked");
  assert.match(marked[0], /Sagar Samman for marine research/);
  assert.doesNotMatch(marked[0], /long walks/, "the sentence with no confirmed claim behind it stays plain");
  await toggle.click();
  assert.equal(await page.locator("p span.bg-verified-soft").count(), 0, "off again");
  await shot("profile-bio-proof");
});
await step("TRANSPARENCY: chain is re-computed in the browser; altering an entry breaks it; undo restores", async () => {
  await page.goto(`${WEB}/transparency`);
  const entries = await (await fetch(`${API}/v1/transparency?limit=500`)).json();
  if (entries.length === 0) { await page.getByText("No certificates issued yet.").waitFor(); return; }
  // nothing is checked until the person asks; then THIS browser re-computes every link
  await page.getByText(/Not checked on this device yet/).waitFor({ timeout: 20000 });
  assert.equal(await page.getByText(/Chain intact/).count(), 0, "no verdict before the button is pressed");
  await page.getByRole("button", { name: "Verify the whole chain in your browser" }).click();
  await page.getByText(/Chain intact/).waitFor({ timeout: 20000 });
  await shot("transparency-intact");
  if (entries.length > 1) {
    await page.getByRole("button", { name: /Alter an entry/ }).click();
    await page.getByText(/Chain broken at entry/).waitFor();
    await page.getByText("First mismatch").waitFor();
    await shot("transparency-broken");
    await page.getByRole("button", { name: "Undo the alteration" }).click();
    await page.getByText(/Chain intact/).waitFor();
  }
});
await step("DEVELOPERS: sections deep-link and tabs follow arrow keys", async () => {
  await page.goto(`${WEB}/developers#play`);
  await page.getByRole("tab", { name: /Playground/ }).waitFor();
  await page.waitForFunction(() => [...document.querySelectorAll('[role=tab]')].some((t) => /Playground/.test(t.textContent) && t.getAttribute("aria-selected") === "true"), null, { timeout: 8000 });
  await page.getByRole("tab", { name: /Playground/ }).focus();
  await page.keyboard.press("ArrowRight");
  await page.waitForFunction(() => location.hash === "#keys", null, { timeout: 4000 });
});
await step("AGENT FLOOR REPLAY: a recorded real run on a demo profile plays station to station and ends in an honest outcome; reduced motion shows it all at once", async () => {
  await page.goto(`${WEB}/mission-control`);
  const section = page.getByRole("region", { name: "Recorded run" });
  await section.getByRole("heading", { name: "Watch it work" }).waitFor({ timeout: 30000 });
  await section.getByText(/Event \d+ of \d+/).waitFor();
  const total = Number((await section.getByText(/Event \d+ of \d+/).innerText()).match(/of (\d+)/)[1]);
  assert.ok(total >= 3, "a real run has several events");
  // with motion it PLAYS: it does not start complete, and it finishes
  await section.getByRole("status").filter({ hasText: /Sealed|With a reviewer|Stopped/ }).waitFor({ timeout: 90000 });
  assert.equal(await section.getByText(`Event ${total} of ${total}`).count(), 1);
  await shot("agent-floor-replay");
  // reduced motion: no playback, everything listed straight away
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`${WEB}/mission-control`);
  await section.getByText(`Event ${total} of ${total}`).waitFor({ timeout: 15000 });
  await section.getByRole("status").filter({ hasText: /Sealed|With a reviewer|Stopped/ }).waitFor({ timeout: 5000 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
});
await step("AGENT FLOOR: pipeline lists the five agents in order, each with a text status", async () => {
  await page.goto(`${WEB}/mission-control`);
  const pipe = page.getByRole("list", { name: "Order of work" });
  await pipe.waitFor();
  for (const n of ["Saathi", "Khoji-Pehle", "Lipik", "Pariksha", "Prahari"]) await pipe.getByText(n, { exact: true }).waitFor();
  assert.ok((await pipe.getByText("Idle").count()) + (await pipe.getByText("Working").count()) >= 5);
  await shot("agent-floor");
});
await step("RESPONSIVE: no page scrolls sideways at 360, 390, 768, 1024 or 1280 px", async () => {
  const paths = ["/", "/directory", slug ? `/p/${slug}` : "/directory", "/transparency", "/developers", "/mission-control", "/verify"];
  const bad = [];
  for (const w of [360, 390, 768, 1024, 1280]) {
    await page.setViewportSize({ width: w, height: 800 });
    for (const path of paths) {
      await page.goto(`${WEB}${path}`, { timeout: 90000 });
      await page.waitForTimeout(1800);
      const m = await page.evaluate(() => ({ s: document.documentElement.scrollWidth, c: document.documentElement.clientWidth }));
      if (m.s > m.c) bad.push(`${path} @${w}: ${m.s} > ${m.c}`);
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  assert.deepEqual(bad, [], "pages that scroll sideways");
});
await step("ONBOARDING (signed out): sends the visitor to sign in rather than showing a broken page", async () => {
  await page.goto(`${WEB}/onboard`, { timeout: 90000, waitUntil: "commit" });
  await page.waitForURL(/\/auth/);
});

await browser.close();
if (errors.length) { console.error("\nBrowser errors:\n" + errors.join("\n")); process.exit(1); }
console.log("\nPages smoke test passed.");
