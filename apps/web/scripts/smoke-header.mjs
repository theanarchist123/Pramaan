// The floating, transparent navigation (v3: logo, tabs, search and account, all floating at the top), in a real browser. Does not need the API.
// node scripts/smoke-header.mjs [webUrl]
// Rewritten from the v2 header test: there is no header bar or phone tab bar any more, so the old assertions (four text links,
// header compresses on scroll, tab bar count) cannot hold. The intent is kept: the places you can go, settings that really change the page,
// nothing sideways on a phone, and the nav never covering the end of the page.
import { chromium } from "playwright";
import assert from "node:assert/strict";

const WEB = process.argv[2] ?? "http://localhost:3000";
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
await d.getByRole("link", { name: "Find people" }).first().waitFor();

await step("the tabs offer Find people, Get listed, Check and a More menu; the current place is marked", async () => {
  const dock = d.getByRole("navigation", { name: "Primary" }).first();
  const names = (await dock.getByRole("link").allTextContents()).map((x) => x.trim());
  assert.deepEqual(names, ["Find people", "Get listed", "Check"]);
  assert.equal(await dock.getByRole("link", { name: "Find people" }).getAttribute("aria-current"), "page");
  assert.equal(await dock.getByText("Mission Control").count(), 0);
  await dock.getByRole("button", { name: "More" }).click();
  await d.getByRole("menuitem", { name: "Transparency" }).waitFor();
  await d.getByRole("menuitem", { name: "Developers" }).waitFor();
  await d.keyboard.press("Escape");
});

await step("there is no bar: the floating pieces have no background fill", async () => {
  const fills = await d.evaluate(() => {
    const root = document.querySelector("[data-floating-nav]");
    return [...root.querySelectorAll("button, a, nav, div")]
      .filter((el) => getComputedStyle(el).position === "fixed" || el.closest("nav, [class*='fixed']"))
      .map((el) => getComputedStyle(el).backgroundColor)
      .filter((c) => c !== "rgba(0, 0, 0, 0)" && c !== "transparent");
  });
  // the active dock item and the avatar may tint; the containers themselves must be clear
  const containers = await d.evaluate(() => [...document.querySelectorAll("[data-floating-nav] > *")].map((el) => getComputedStyle(el).backgroundColor));
  assert.ok(containers.every((c) => c === "rgba(0, 0, 0, 0)"), `containers must be transparent, got ${containers.join(", ")}`);
  assert.ok(Array.isArray(fills));
});

await step("the account menu folds in dark mode, larger text and reduce motion, and each really changes the page", async () => {
  await d.getByRole("button", { name: "Account and settings" }).click();
  await d.getByRole("menuitemcheckbox", { name: "Dark mode" }).click();
  await d.waitForFunction(() => document.documentElement.classList.contains("dark"));
  await d.getByRole("menuitemcheckbox", { name: "Larger text" }).click();
  await d.waitForFunction(() => document.documentElement.dataset.largeText === "true");
  await d.getByRole("menuitemcheckbox", { name: "Reduce motion" }).click();
  await d.waitForFunction(() => document.documentElement.dataset.reduceMotion === "true");
  assert.equal(await d.getByRole("menuitemcheckbox", { name: "Dark mode" }).getAttribute("aria-checked"), "true");
  assert.equal(await d.getByRole("menuitemcheckbox", { name: "Larger text" }).getAttribute("aria-checked"), "true");
  await d.getByRole("menuitem", { name: /Sign in/ }).waitFor();
  assert.equal(await d.getByRole("menuitem", { name: /Sign out/ }).count(), 0);
  await d.keyboard.press("Escape");
  await d.screenshot({ path: "smoke-shots/header-desktop.png" });
});

await step("the search piece opens the command palette, which can reach every main place", async () => {
  await d.locator("[data-floating-nav]").getByRole("button", { name: "Search" }).click();
  await d.getByPlaceholder(/Go anywhere/).waitFor();
  for (const label of ["Get listed", "Check a certificate", "Find people", "My page"]) {
    await d.getByRole("option", { name: new RegExp(label) }).first().waitFor();
  }
  assert.equal(await d.getByRole("option", { name: /Mission Control/ }).count(), 0, "Mission Control is not a public place");
  await d.keyboard.press("Escape");
});

await step("scrolling down hides the pieces and scrolling up brings them back", async () => {
  await d.evaluate(() => { document.body.style.minHeight = "4000px"; window.scrollTo(0, 0); });
  await d.waitForTimeout(300);
  await d.mouse.wheel(0, 900);
  await d.waitForTimeout(700);
  const hidden = await d.locator("[data-floating-nav] > div").first().evaluate((el) => Number(getComputedStyle(el).opacity));
  assert.ok(hidden < 0.5, `dock should hide while reading down (opacity ${hidden})`);
  await d.mouse.wheel(0, -300);
  await d.waitForTimeout(700);
  const shown = await d.locator("[data-floating-nav] > div").first().evaluate((el) => Number(getComputedStyle(el).opacity));
  assert.ok(shown > 0.5, `dock should return on scrolling up (opacity ${shown})`);
});

const m = await newPage(390, 800);
await m.goto(`${WEB}/directory`);
await step("phone: the tabs sit on a second row at the top, inside the screen, and nothing scrolls sideways", async () => {
  const nav = m.getByRole("navigation", { name: "Primary" }).last();
  await nav.waitFor();
  assert.equal(await nav.isVisible(), true);
  assert.equal(await nav.getByRole("link").count(), 3);
  const box = await nav.getByRole("link").last().boundingBox();
  assert.ok(box.x >= 0 && box.x + box.width <= 390, "tabs must stay inside the screen");
  assert.ok(box.y < 140, "tabs are at the top of the page, not the bottom");
  const w = await m.evaluate(() => ({ s: document.documentElement.scrollWidth, c: document.documentElement.clientWidth }));
  assert.ok(w.s <= w.c, `no horizontal scroll (${w.s} > ${w.c})`);
  await m.screenshot({ path: "smoke-shots/header-mobile.png" });
});

await step("phone: the account menu is reachable", async () => {
  await m.evaluate(() => window.scrollTo(0, 0));
  await m.getByRole("button", { name: "Account and settings" }).click();
  await m.getByRole("menuitemcheckbox", { name: "Dark mode" }).waitFor();
});

await browser.close();
console.log("\nHeader smoke test passed.");
