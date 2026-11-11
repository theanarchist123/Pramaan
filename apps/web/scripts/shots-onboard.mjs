// Signed-in onboarding screenshots (consent step, then the split screen), desktop + phone. Needs the API with email verification not required.
import { chromium } from "playwright";
import { randomBytes } from "node:crypto";
import { mkdirSync } from "node:fs";
const WEB = process.argv[2] ?? "http://localhost:3012", API = process.argv[3] ?? "http://localhost:8010";
mkdirSync("smoke-shots/review", { recursive: true });
const email = `ob-${randomBytes(3).toString("hex")}@example.com`;
const J = { "Content-Type": "application/json" };
const r = await fetch(`${API}/v1/auth/register`, { method: "POST", headers: J, body: JSON.stringify({ email, password: "password123", name: "Review Person" }) });
if (r.status !== 201) throw new Error("register " + r.status);
const b = await chromium.launch();
for (const [mode, w, h] of [["desktop", 1280, 900], ["mobile", 390, 800]]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h } });
  const login = await ctx.request.post(`${API}/v1/auth/login`, { data: { email, password: "password123" } });
  if (!login.ok()) throw new Error("login " + login.status());
  const p = await ctx.newPage();
  p.on("pageerror", (e) => console.log("PE", e.message.slice(0, 150)));
  await p.goto(`${WEB}/onboard`, { timeout: 90000 });
  await p.waitForTimeout(4000);
  await p.screenshot({ caret: "initial", path: `smoke-shots/review/onboard-${mode}-1-consent.png` });
  const consent = p.getByText("List my verified profile publicly.");
  const start = p.getByRole("button", { name: /Start talking/i });
  if (await consent.count()) {
    await consent.click();
    await p.getByRole("textbox").first().fill("Review Person"); await start.click().catch(() => {}); await p.waitForTimeout(5000); }
  await p.screenshot({ caret: "initial", path: `smoke-shots/review/onboard-${mode}-2-chat.png` });
  console.log("shot", mode, p.url());
  await ctx.close();
}
await b.close();
