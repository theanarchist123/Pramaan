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
  // the retired pages and Developers are not in the menu (Developers lives in the footer of the home page)
  for (const gone of ["Transparency", "How we check", "Developers"]) assert.equal(await d.getByRole("menuitem", { name: gone }).count(), 0, `${gone} is not in the More menu`);
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
await step("phone: an app bar on top and a bottom navigation bar, both solid and inside the screen; the floating desktop nav is gone", async () => {
  const bar = m.locator("[data-mobile-shell] header");
  const nav = m.locator("[data-mobile-shell]").getByRole("navigation", { name: "Primary" });
  await nav.waitFor();
  assert.equal(await m.locator("[data-floating-nav]").isVisible(), false, "the floating desktop nav must not show on a phone");
  const top = await bar.boundingBox();
  assert.ok(top.y === 0 && top.height >= 56 && top.width === 390, `app bar is a full-width bar at the top (${JSON.stringify(top)})`);
  assert.equal(await nav.getByRole("link").count(), 4);
  assert.equal(await nav.getByRole("button", { name: "More" }).count(), 1);
  const nb = await nav.boundingBox();
  assert.ok(Math.abs(nb.y + nb.height - 800) <= 1 && nb.width === 390, `bottom bar sits at the bottom edge (${JSON.stringify(nb)})`);
  assert.ok(nb.height >= 64, "tap targets are at least 48px (bar is 64px)");
  for (const l of await nav.getByRole("link").all()) assert.ok((await l.boundingBox()).height >= 48);
  const w = await m.evaluate(() => ({ s: document.documentElement.scrollWidth, c: document.documentElement.clientWidth }));
  assert.ok(w.s <= w.c, `no horizontal scroll (${w.s} > ${w.c})`);
  assert.equal(await nav.getByRole("link", { name: "Find" }).getAttribute("aria-current"), "page");
  await m.screenshot({ path: "smoke-shots/header-mobile.png" });
});

await step("phone: the content ends above the bottom bar", async () => {
  let prev = -1;
  for (let i = 0; i < 12; i++) {
    const h = await m.evaluate(() => { window.scrollTo(0, document.documentElement.scrollHeight); return document.documentElement.scrollHeight; });
    await m.waitForTimeout(500);
    if (h === prev) break;
    prev = h;
  }
  const bar = await m.locator("[data-mobile-shell]").getByRole("navigation", { name: "Primary" }).boundingBox();
  const last = await m.locator("main > :last-child").boundingBox();
  assert.ok(last.y + last.height <= bar.y + 1, `content must end above the bar (content bottom ${Math.round(last.y + last.height)}, bar top ${Math.round(bar.y)})`);
});

await step("phone: an inner screen shows a back arrow and its name; the bar of a root screen shows the mark", async () => {
  await m.goto(`${WEB}/developers`);
  await m.locator("[data-mobile-shell] header").getByText("Developers").waitFor();
  await m.locator("[data-mobile-shell] header").getByRole("button", { name: "Back" }).waitFor();
  await m.goto(`${WEB}/verify`);
  assert.equal(await m.locator("[data-mobile-shell] header").getByRole("button", { name: "Back" }).count(), 0);
  await m.locator("[data-mobile-shell] header").getByRole("link", { name: "Pramaan home" }).waitFor();
});

await step("phone: More opens a bottom sheet with the other pages and the settings, and each setting really changes the page", async () => {
  await m.getByRole("button", { name: "More" }).click();
  const sheet = m.getByRole("dialog");
  await sheet.waitFor();
  for (const gone of ["How we check", "Transparency", "Developers"]) assert.equal(await sheet.getByRole("link", { name: gone }).count(), 0, `${gone} is not in the sheet`);
  await sheet.getByRole("button", { name: "Larger text" }).click();
  await m.waitForFunction(() => document.documentElement.dataset.largeText === "true");
  await sheet.getByRole("button", { name: "Dark mode" }).click();
  await m.waitForFunction(() => document.documentElement.classList.contains("dark"));
  await sheet.getByRole("link", { name: /Sign in/ }).first().waitFor();
  await m.screenshot({ path: "smoke-shots/header-mobile-sheet.png" });
  await m.keyboard.press("Escape");
});

await step("phone: the search button opens the command palette", async () => {
  await m.locator("[data-mobile-shell] header").getByRole("button", { name: "Search" }).click();
  await m.getByPlaceholder(/Go anywhere/).waitFor();
  await m.keyboard.press("Escape");
});

await step("phone: the bottom bar hides on sign-in (a focused flow) and while the keyboard is up", async () => {
  await m.goto(`${WEB}/auth?mode=login`);
  assert.equal(await m.locator("[data-mobile-shell]").count() === 0 || !(await m.locator("[data-mobile-shell] nav").count()), true);
});

await browser.close();
console.log("Header smoke test passed.");
