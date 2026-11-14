// Signed-in onboarding in a real browser: consent, start, a real conversation turn, and FACT CAPTURE (M-03): the exact words a fact was
// recorded from are marked in the person's own message. Needs the API (LLM_MODE=mock) + web app + local docker DB.
//   node scripts/smoke-onboard.mjs [webUrl] [apiUrl]
import { chromium } from "playwright";
import { randomBytes } from "node:crypto";
import { mkdirSync } from "node:fs";
import assert from "node:assert/strict";

const WEB = process.argv[2] ?? "http://localhost:3013", API = process.argv[3] ?? "http://localhost:8010";
mkdirSync("smoke-shots", { recursive: true });
const email = `fc-${randomBytes(3).toString("hex")}@example.com`;
const reg = await fetch(`${API}/v1/auth/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: "password123", name: "Fact Capture" }) });
assert.equal(reg.status, 201);

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
assert.ok((await ctx.request.post(`${API}/v1/auth/login`, { data: { email, password: "password123" } })).ok(), "login");
const page = await ctx.newPage();
page.setDefaultNavigationTimeout(90000);
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const step = async (n, fn) => { process.stdout.write(`• ${n} … `); await fn(); console.log("ok"); };

await step("consent, then Saathi greets you", async () => {
  await page.goto(`${WEB}/onboard`);
  await page.getByText("List my verified profile publicly.").click();
  await page.getByRole("textbox").first().fill("Fact Capture");
  await page.getByRole("button", { name: /Start talking/i }).click();
  await page.getByText(/May I know your full name/).waitFor({ timeout: 30000 });
});

const SAID = "I received the Sagar Samman award for marine research in 2024.";
await step("what you say becomes a fact on your profile, and the words it came from are marked in your message", async () => {
  await page.getByPlaceholder(/Type or tap the mic/).fill(`I am a marine scientist working in Kerala. ${SAID}`);
  await page.getByPlaceholder(/Type or tap the mic/).press("Enter");
  // the claim lands on the profile (right-hand side) ...
  await page.getByText(/Sagar Samman award/).first().waitFor({ timeout: 30000 });
  // ... and the person's OWN words behind it are marked, with a screen-reader note
  const marks = page.locator("mark");
  await marks.first().waitFor({ timeout: 60000 }); // the reply (and so the highlight) can take a while on a cold start
  const texts = await marks.allTextContents();
  assert.ok(texts.length >= 1, "at least one stretch is marked");
  for (const t of texts) {
    const literal = t.replace(" (recorded on your profile)", "").trim();
    assert.ok(`I am a marine scientist working in Kerala. ${SAID}`.toLowerCase().includes(literal.toLowerCase()), `marked text must be a literal part of what was said: "${literal}"`);
  }
  assert.match(texts.join(" "), /recorded on your profile/);
  await page.screenshot({ caret: "initial", path: "smoke-shots/onboard-fact-capture.png" });
});
// v3: the stepper became the journey + "Next step" card. Same intent: chatting alone submits nothing; the next step is to back a claim with a document.
await step("nothing is submitted by chatting: the next step is a document, and the journey is not at review", async () => {
  await page.getByRole("heading", { name: /Back one achievement with a document/ }).waitFor({ timeout: 30000 });
  assert.equal(await page.getByText(/With a reviewer|Checking your facts/).count(), 0, "chatting must not start a review");
  const current = page.locator('[aria-current="step"]');
  await current.first().waitFor();
  assert.match(await current.first().innerText(), /Add a document/);
});

await browser.close();
assert.deepEqual(errors, [], "no page errors");
console.log("\nFact capture smoke test passed.");
