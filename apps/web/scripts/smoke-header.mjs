// The site header and the phone tab bar (spec 6.0), in a real browser. Does not need the API. node scripts/smoke-header.mjs [webUrl]
import { chromium } from "playwright";
import assert from "node:assert/strict";

const WEB = process.argv[2] ?? "http://localhost:3013";
const browser = await chromium.launch();
const step = async (n, fn) => { process.stdout.write(`• ${n} … `); await fn(); console.log("ok"); };
const newPage = async (w, h) => {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, bypassCSP: true });
  const page = await ctx.newPage();
  page.setDefaultNavigationTimeout(90000);
  return page;
};

const d = await newPage(1280, 800);
await d.goto(`${WEB}/directory`);
await d.getByRole("link", { name: "Directory" }).first().waitFor();

await step("the public nav is four places: Directory, Verify, Transparency, Developers (no Mission Control)", async () => {
  const nav = d.getByRole("navigation", { name: "Primary" }).first();
  const names = await nav.getByRole("link").allTextContents();
  assert.deepEqual(names.map((x) => x.trim()), ["Directory", "Verify", "Transparency", "Developers"]);
  assert.equal(await d.getByRole("navigation", { name: "Primary" }).first().getByText("Mission Control").count(), 0);
  assert.equal(await nav.getByRole("link", { name: "Directory" }).getAttribute("aria-current"), "page");
});

await step("the account menu folds in dark mode, larger text and reduce motion, and each really changes the page", async () => {
  // The menu stays open after a checkbox is ticked (so several settings can be changed in one visit): open it once.
  await d.getByRole("button", { name: "Account and settings" }).click();
  await d.getByRole("menuitemcheckbox", { name: "Dark mode" }).click();
  await d.waitForFunction(() => document.documentElement.classList.contains("dark"));
  await d.getByRole("menuitemcheckbox", { name: "Larger text" }).click();
  await d.waitForFunction(() => document.documentElement.dataset.largeText === "true");
  await d.getByRole("menuitemcheckbox", { name: "Reduce motion" }).click();
  await d.waitForFunction(() => document.documentElement.dataset.reduceMotion === "true");
  // the checkboxes now report their state
  assert.equal(await d.getByRole("menuitemcheckbox", { name: "Dark mode" }).getAttribute("aria-checked"), "true");
  assert.equal(await d.getByRole("menuitemcheckbox", { name: "Larger text" }).getAttribute("aria-checked"), "true");
  // signed out: the menu offers sign-in, not sign-out
  await d.getByRole("menuitem", { name: /Sign in/ }).waitFor();
  assert.equal(await d.getByRole("menuitem", { name: /Sign out/ }).count(), 0);
  await d.keyboard.press("Escape");
  await d.screenshot({ path: "smoke-shots/header-desktop.png" });
});

await step("the header compresses once the page has scrolled", async () => {
  await d.evaluate(() => window.scrollTo(0, 0));
  await d.waitForTimeout(300);
  const tall = (await d.locator("header").first().boundingBox()).height;
  await d.evaluate(() => { document.body.style.minHeight = "3000px"; window.scrollTo(0, 600); });
  await d.waitForTimeout(500);
  const short = (await d.locator("header").first().boundingBox()).height;
  assert.ok(short < tall, `header should shrink on scroll (${tall} -> ${short})`);
});

const m = await newPage(390, 800);
await m.goto(`${WEB}/directory`);
await step("phone: a bottom tab bar with four tabs, the top nav hidden, and nothing sideways", async () => {
  const tabs = m.getByRole("navigation", { name: "Primary" }).last();
  await tabs.waitFor();
  assert.equal(await tabs.isVisible(), true);
  const labels = (await tabs.locator("li").allTextContents()).map((x) => x.trim());
  assert.equal(labels.length, 4);
  assert.match(labels[2], /Get listed/, "signed out, the third tab invites you to get listed");
  assert.equal(await m.locator("header nav").isVisible(), false, "the desktop nav is hidden on phones");
  const w = await m.evaluate(() => ({ s: document.documentElement.scrollWidth, c: document.documentElement.clientWidth }));
  assert.ok(w.s <= w.c, `no horizontal scroll (${w.s} > ${w.c})`);
});

await step("phone: the tab bar never covers the end of the page", async () => {
  // Pages grow as lazy content loads while you scroll, so keep scrolling until the page stops growing (a single jump can stop short of the real end).
  let prev = -1;
  for (let i = 0; i < 12; i++) {
    const h = await m.evaluate(() => { window.scrollTo(0, document.documentElement.scrollHeight); return document.documentElement.scrollHeight; });
    await m.waitForTimeout(500);
    if (h === prev) break;
    prev = h;
  }
  const bar = await m.getByRole("navigation", { name: "Primary" }).last().boundingBox();
  // main reserves bottom padding for the bar, so measure the last piece of CONTENT, which must end above the bar
  const last = await m.locator("main > :last-child").boundingBox();
  assert.ok(last.y + last.height <= bar.y + 1, `content must end above the bar (content bottom ${Math.round(last.y + last.height)}, bar top ${Math.round(bar.y)})`);
  await m.screenshot({ path: "smoke-shots/header-mobile.png" });
});

await step("phone: the account menu is still reachable from the top bar", async () => {
  await m.evaluate(() => window.scrollTo(0, 0));
  await m.getByRole("button", { name: "Account and settings" }).click();
  await m.getByRole("menuitemcheckbox", { name: "Dark mode" }).waitFor();
});

await browser.close();
console.log("\nHeader smoke test passed.");
