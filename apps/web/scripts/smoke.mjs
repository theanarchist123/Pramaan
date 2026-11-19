// End-to-end smoke test of the whole journey against a running API (LLM_MODE=mock) + web app: register, talk, check, document, approval, certificate, forgery, log.
// Needs the API started with REQUIRE_EMAIL_VERIFICATION=false (it registers fresh users and does not verify their e-mail) and, to reach the auto-approve path,
// HUMAN_APPROVAL_FIRST_LISTING=false AWARD_CLAIMS_NEED_HUMAN=false (by default a first listing and any award claim go to a person, by design).
// Usage: node scripts/smoke.mjs [baseUrl] [outDir]   (updated for the v3 UI: no tabs; one journey with sections; the account menu holds sign-out)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.argv[2] ?? "http://localhost:3100";
const OUT = process.argv[3] ?? "smoke-shots";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1360, height: 860 } });
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => {
  // The deliberately fake certificate code legitimately produces a 404 in the console.
  if (m.type() === "error" && !m.text().includes("404") && !m.text().includes("401")) errors.push(`console: ${m.text()}`);
});

const step = async (name, fn) => {
  process.stdout.write(`• ${name} … `);
  await fn();
  console.log("ok");
};

await step("landing renders", async () => {
  await page.goto(BASE);
  await page.getByRole("heading", { level: 1, name: /achievers/i }).waitFor();
  await page.getByRole("heading", { name: /Meet people who/ }).waitFor();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/01-landing.png`, fullPage: true });
});

await step("register", async () => {
  await page.goto(`${BASE}/auth?next=/onboard`);
  await page.getByLabel("Your name").fill("Smoke Tester");
  await page.getByLabel("Email").fill(`smoke-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/\/onboard/);
});

await step("consent step", async () => {
  await page.getByRole("heading", { level: 1, name: /build your/i }).waitFor();
  await page.screenshot({ path: `${OUT}/02-consent.png` });
  await page.getByText("List my verified profile publicly.").click();
  await page.getByRole("button", { name: "Start talking to Saathi" }).click();
  await page.getByText(/I'm Saathi/).waitFor();
});

await step("chat builds the profile live", async () => {
  const box = page.getByLabel("Your message");
  await box.fill("My name is Meera Iyer");
  await box.press("Enter");
  await page.getByRole("heading", { name: "Meera Iyer" }).waitFor();
  await box.fill("I am a marine scientist working in Kerala. I received the Sagar Samman award in 2024.");
  await box.press("Enter");
  await page.getByText("Self-claimed").first().waitFor();
  await page.getByRole("heading", { name: /Back one achievement with a document/ }).waitFor({ timeout: 30000 }); // the "next step" card follows the profile
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/03-onboarding.png` });
});

await step("verify streams agents", async () => {
  await page.getByRole("button", { name: "Verify my profile" }).click(); // v3: one page, no tabs; the check section is on the right
  await page.getByText("With a reviewer").first().waitFor({ timeout: 30000 }); // wording per the "never say verified unless the server says so" rule
  await page.getByText(/Identity not confirmed|no supporting evidence/).first().waitFor();
  await page.screenshot({ path: `${OUT}/04-verify.png` });
});

await step("second person: matching document → auto-approved", async () => {
  await page.getByRole("button", { name: "Account and settings" }).click(); // v3: sign-out lives in the account menu
  await page.getByRole("menuitem", { name: /Sign out/ }).click();
  await page.waitForTimeout(600);
  await page.goto(`${BASE}/auth?next=/onboard`);
  await page.getByLabel("Your name").fill("Doc Tester");
  await page.getByLabel("Email").fill(`smoke-doc-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/\/onboard/);
  await page.getByText("List my verified profile publicly.").click();
  await page.getByRole("button", { name: "Start talking to Saathi" }).click();
  const box = page.getByLabel("Your message");
  await box.fill("My name is Arjun Rao");
  await box.press("Enter");
  await page.getByRole("heading", { name: "Arjun Rao" }).waitFor();
  await box.fill("I am an engineer in Karnataka. I received the Karnataka Innovation Award in 2023.");
  await box.press("Enter");
  await page.getByText("Self-claimed").first().waitFor();

  await page.locator('input[type="file"]').last().setInputFiles({ // the first file input is the photo; the document drop is the last
    name: "award.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(`Type: award letter\nName: Arjun Rao\nTitle: Karnataka Innovation Award\nIssuer: Government of Karnataka\nYear: 2023
Reference: ${Date.now()}
`), // unique per run: an identical document is (correctly) flagged as a duplicate
  });
  await page.getByText(/holder: Arjun Rao/).waitFor({ timeout: 20000 });
  await page.screenshot({ path: `${OUT}/04b-document.png` });

  await page.getByRole("button", { name: "Verify my profile" }).click();
  await page.getByText("Passed automated checks").first().waitFor({ timeout: 30000 });
  await page.screenshot({ path: `${OUT}/04c-approved.png` });
});

let certCode = "";
await step("issue a signed certificate", async () => {
  await page.getByRole("button", { name: "Issue my signed certificate" }).click();
  const open = page.locator('a:has-text("Open verification page")');
  await open.waitFor({ timeout: 20000 });
  certCode = (await open.getAttribute("href")).split("/").pop();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/04d-certificate-card.png` });
});

await step("verification page shows every check", async () => {
  await page.goto(`${BASE}/verify/${certCode}`);
  await page.getByRole("heading", { name: "Authentic" }).waitFor();
  await page.getByText(/Found at position #\d+ of \d+/).waitFor();
  await page.getByText("Confirmed it has not been revoked").waitFor();
  await page.waitForTimeout(2200);
  await page.screenshot({ path: `${OUT}/07-verify-page.png`, fullPage: true });
});

await step("PDF + PNG render via headless Chromium", async () => {
  const API = process.env.API ?? "http://localhost:8000";
  const pdf = await fetch(`${API}/v1/certificates/${certCode}/pdf`);
  const png = await fetch(`${API}/v1/certificates/${certCode}/image.png`);
  const pdfBytes = Buffer.from(await pdf.arrayBuffer());
  if (pdf.status !== 200 || !pdfBytes.subarray(0, 4).equals(Buffer.from("%PDF"))) throw new Error(`bad pdf (${pdf.status})`);
  if (png.status !== 200) throw new Error(`bad png (${png.status})`);
  const { writeFileSync } = await import("node:fs");
  writeFileSync(`${OUT}/certificate.pdf`, pdfBytes);
  writeFileSync(`${OUT}/certificate.png`, Buffer.from(await png.arrayBuffer()));
  process.stdout.write(`(pdf ${(pdfBytes.length / 1024).toFixed(0)} KB) `);
});

await step("try to forge: edit an award → forgery detected", async () => {
  await page.goto(`${BASE}/verify/${certCode}`);
  await page.getByRole("button", { name: "Edit as a forger" }).click(); // the editing form opens on request
  await page.getByLabel("Achievement 1").fill("Padma Vibhushan 2025");
  await page.getByText("Forgery detected").waitFor({ timeout: 10000 });
  await page.getByText(/pinpointed what you changed/).waitFor();
  await page.getByText("NOT VALID").first().waitFor();
  await page.getByLabel("Achievement 1").scrollIntoViewIfNeeded();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/08-forgery.png` });
  await page.getByRole("button", { name: "Reset" }).click();
  await page.getByText("Nothing changed yet").waitFor();
});

await step("a made-up code is rejected", async () => {
  await page.goto(`${BASE}/verify/PRM-FAKEFAKE12`);
  await page.getByRole("heading", { name: "Not found" }).waitFor();
  await page.screenshot({ path: `${OUT}/09-not-found.png` });
});

await step("dark mode", async () => {
  await page.getByRole("button", { name: "Account and settings" }).click();
  await page.getByRole("menuitemcheckbox", { name: "Dark mode" }).click();
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/05-dark.png` });
});

await step("mobile layout", async () => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(BASE);
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/06-mobile.png`, fullPage: false });
});

await browser.close();
if (errors.length) {
  console.log("\nBrowser errors:\n" + errors.join("\n"));
  process.exitCode = 1;
} else console.log("\nNo browser errors.");
