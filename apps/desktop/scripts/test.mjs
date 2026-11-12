// Tests for the desktop shell: pure link parsing, then the REAL Electron app driven by Playwright.
// Self-contained: serves its own stand-in "Pramaan" so no database or API is needed.   Run: node scripts/test.mjs
import { _electron as electron } from "playwright";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { resolveDeepLink, findDeepLink, pathFromClipboard } = require("../src/links.js");
// PRAMAAN_EXE=<path to Pramaan.exe> runs this same suite against the PACKAGED app instead of the dev one.
const packaged = process.env.PRAMAAN_EXE || null;
const electronPath = packaged || require("electron");
const appArgs = packaged ? [] : [path.resolve(import.meta.dirname, "..")];
const ROOT = path.resolve(import.meta.dirname, "..");

let passed = 0;
const step = async (name, fn) => {
  process.stdout.write(`• ${name} … `);
  await fn();
  passed++;
  console.log("ok");
};

await step("verifier mode: one code in any copied text opens its check; none or two does not", () => {
  assert.equal(pathFromClipboard("Please check prm-abcdefghjk before Friday"), "/verify/PRM-ABCDEFGHJK");
  assert.equal(pathFromClipboard("PRM-ABCDEFGHJK and again PRM-ABCDEFGHJK"), "/verify/PRM-ABCDEFGHJK");
  assert.equal(pathFromClipboard("PRM-ABCDEFGHJK vs PRM-ZZZZZZZZZZ"), null);
  assert.equal(pathFromClipboard("nothing here https://evil.example/verify/PRM"), null);
  assert.equal(pathFromClipboard(42), null);
});

// ---------------------------------------------------------------------------------- 1. link parsing
await step("deep links: only exact, well-formed shapes resolve — to paths on our own origin", () => {
  assert.equal(resolveDeepLink("pramaan://verify/PRM-ABCDEFGHJK"), "/verify/PRM-ABCDEFGHJK");
  assert.equal(resolveDeepLink("pramaan://verify/prm-abcdefghjk"), "/verify/PRM-ABCDEFGHJK"); // normalised
  assert.equal(resolveDeepLink("PRAMAAN://VERIFY/PRM-ABCDEFGHJK"), "/verify/PRM-ABCDEFGHJK");
  assert.equal(resolveDeepLink("pramaan://profile/meera-iyer-1a2b"), "/p/meera-iyer-1a2b");
  assert.equal(resolveDeepLink("pramaan://onboard"), "/onboard");
  assert.equal(resolveDeepLink("pramaan://directory/"), "/directory");
  assert.equal(findDeepLink(["electron.exe", ".", "pramaan://verify/PRM-ABCDEFGHJK"]), "pramaan://verify/PRM-ABCDEFGHJK");
  assert.equal(findDeepLink(["--flag", "https://x.y"]), null);
});

await step("deep links: hostile input is rejected", () => {
  const hostile = [
    "pramaan://verify/../../admin", "pramaan://verify/..%2F..%2Fadmin", "pramaan://verify/PRM-1", "pramaan://verify/PRM-ABCDEFGHJK/extra",
    "pramaan://verify/PRM-ABCDEFGHJK?next=https://evil.example", "pramaan://verify/PRM-ABCDEFGHJK#x", "pramaan://user:pw@verify/PRM-ABCDEFGHJK",
    "pramaan://verify:99/PRM-ABCDEFGHJK", "pramaan://profile/%2e%2e", "pramaan://profile/-leading-dash", "pramaan://profile/UPPER",
    "pramaan://profile/" + "a".repeat(200), "pramaan://onboard/extra", "pramaan://evil/x", "pramaan://", "pramaan:verify/PRM-ABCDEFGHJK",
    "https://verify/PRM-ABCDEFGHJK", "javascript:alert(1)", "file:///C:/Windows/win.ini", "pramaan://verify/%E0%A4%A", "", null, undefined, 42, {},
  ];
  for (const h of hostile) assert.equal(resolveDeepLink(h), null, `should reject ${JSON.stringify(h)}`);
});

// ---------------------------------------------------------------------------------- 2. the real app
const listen = (handler, port = 0) =>
  new Promise((resolve) => {
    const s = createServer(handler).listen(port, "127.0.0.1", () => resolve({ s, port: s.address().port }));
  });

const foreignHits = [];
const foreign = await listen((req, res) => {
  foreignHits.push(req.url);
  res.end("<title>foreign</title>foreign site");
});
const FOREIGN = `http://127.0.0.1:${foreign.port}/`;

const page = (title, body = "") => `<!doctype html><title>${title}</title><body><h1>${title}</h1>${body}</body>`;
const appHandler = (req, res) => {
  res.setHeader("Content-Type", "text/html");
  if (req.url === "/") {
    return res.end(page("Pramaan test home", `<a id="blank" href="${FOREIGN}" target="_blank">out</a><a id="same" href="${FOREIGN}">leave</a>`));
  }
  res.end(page(`page ${req.url}`));
};
const app = await listen(appHandler);
const APP = `http://127.0.0.1:${app.port}`;

const dirs = [];
const userData = () => {
  const d = mkdtempSync(path.join(tmpdir(), "pramaan-desktop-"));
  dirs.push(d);
  return d;
};
const env = (extra = {}) => {
  const e = { ...process.env, PRAMAAN_TEST: "1", ...extra };
  delete e.ELECTRON_RUN_AS_NODE;
  return e;
};
const launch = (extra) => electron.launch({ executablePath: electronPath, args: appArgs, env: env(extra), timeout: 60000 });

const UD = userData();
const electronApp = await launch({ PRAMAAN_URL: APP, PRAMAAN_USER_DATA: UD });
const win = await electronApp.firstWindow();
await win.waitForURL(`${APP}/`);
await electronApp.evaluate(({ shell }) => {
  globalThis.__opened = [];
  shell.openExternal = (u) => (globalThis.__opened.push(u), Promise.resolve()); // never open a real browser in a test
});
const opened = () => electronApp.evaluate(() => globalThis.__opened);
const fire = (...argv) => electronApp.evaluate(({ app: a }, args) => a.emit("second-instance", {}, args), ["electron.exe", ".", ...argv]);

try {
  await step("loads the configured server in a hardened window", async () => {
    assert.equal(await win.title(), "Pramaan test home");
    const prefs = await electronApp.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences());
    assert.equal(prefs.contextIsolation, true);
    assert.equal(prefs.nodeIntegration, false);
    assert.equal(prefs.sandbox, true);
    assert.equal(prefs.webviewTag, false);
  });

  await step("the page has no Node/Electron access — only the tiny desktop bridge", async () => {
    const seen = await win.evaluate(() => ({
      require: typeof require, process: typeof process, electron: typeof electron,
      bridge: Object.keys(window.pramaanDesktop || {}).sort(), isDesktop: window.pramaanDesktop?.isDesktop,
    }));
    assert.deepEqual(seen, { require: "undefined", process: "undefined", electron: "undefined", bridge: ["isDesktop", "platform", "retry"], isDesktop: true });
  });

  await step("links to other sites open in the real browser, never inside the app window", async () => {
    await win.click("#blank");
    await win.waitForTimeout(500);
    assert.deepEqual(await opened(), [FOREIGN]);
    assert.equal((await electronApp.windows()).length, 1);
    assert.equal(win.url(), `${APP}/`);
  });

  await step("in-window navigation to another origin is blocked (and handed to the browser)", async () => {
    await win.click("#same", { noWaitAfter: true }); // the navigation is (correctly) cancelled: don't wait for it
    await win.waitForTimeout(500);
    assert.equal(win.url(), `${APP}/`);
    assert.equal((await opened()).length, 2);
    assert.deepEqual(foreignHits, [], "the app window must never have fetched the foreign site");
  });

  await step("file:, data:, blob: and OS-level schemes can't steer the window or reach the OS", async () => {
    const before = (await opened()).length;
    const real = () => electronApp.evaluate(({ BrowserWindow }) => {
      const wc = BrowserWindow.getAllWindows()[0].webContents;
      return { url: wc.getURL(), title: wc.getTitle() };
    });
    // (javascript: is deliberately absent: script the page runs against ITSELF is not something the shell can
    //  or should prevent. What matters is that the window can't be steered to another origin or to the OS.)
    for (const url of ["file:///C:/Windows/win.ini", "ms-msdt:/id", "vscode://x", "data:text/html,<title>DATA</title>x", "blob:http://x/y"]) {
      await win.goto(`${APP}/`);
      await win.evaluate((u) => { setTimeout(() => { location.href = u; }, 0); }, url);
      await win.waitForTimeout(600);
      const now = await real();
      assert.equal(now.url, `${APP}/`, `window was steered by ${url}`);
      assert.equal(now.title, "Pramaan test home", `document was replaced by ${url}`);
    }
    assert.equal((await opened()).length, before, "non-web schemes must never reach shell.openExternal");
  });

  await step("a valid deep link navigates the window; hostile ones are ignored", async () => {
    await fire("pramaan://verify/prm-abc123xyz9");
    await win.waitForURL(`${APP}/verify/PRM-ABC123XYZ9`);
    await fire("pramaan://profile/meera-iyer-1a2b");
    await win.waitForURL(`${APP}/p/meera-iyer-1a2b`);
    const stay = win.url();
    for (const bad of ["pramaan://verify/..%2F..%2Fadmin", "pramaan://evil/x", "pramaan://verify/PRM-1", "pramaan://verify/PRM-ABCDEFGHJK?next=https://evil.example"]) {
      await fire(bad);
    }
    await win.waitForTimeout(700);
    assert.equal(win.url(), stay);
    assert.deepEqual(foreignHits, []);
  });

  await step("every permission request is denied (camera, location, notifications…)", async () => {
    const states = await win.evaluate(async () => {
      const out = {};
      for (const name of ["geolocation", "notifications", "camera", "microphone"]) {
        try { out[name] = (await navigator.permissions.query({ name })).state; } catch { out[name] = "unsupported"; }
      }
      return out;
    });
    for (const [name, state] of Object.entries(states)) assert.notEqual(state, "granted", `${name} must not be granted (${state})`);
  });

  await step("a second launch hands over to the running app and exits (single instance)", async () => {
    const child = spawn(electronPath, [...appArgs, "pramaan://verify/PRM-SECONDLNCH"], {
      env: env({ PRAMAAN_URL: APP, PRAMAAN_USER_DATA: UD }), stdio: "ignore",
    });
    const code = await new Promise((resolve, reject) => {
      const t = setTimeout(() => (child.kill(), reject(new Error("second instance did not exit"))), 30000);
      child.on("exit", (c) => (clearTimeout(t), resolve(c)));
    });
    assert.equal(code, 0);
    await win.waitForURL(`${APP}/verify/PRM-SECONDLNCH`); // the FIRST window received the second launch's link
  });
} finally {
  await electronApp.close();
}

// ---------------------------------------------------------------------------------- 3. offline + retry
await step("server unreachable → friendly offline screen; 'Try again' recovers once it's back", async () => {
  const probe = await listen(() => {});
  const port = probe.port;
  await new Promise((r) => probe.s.close(r)); // nothing listens on this port now
  const URL_ = `http://127.0.0.1:${port}`;
  const offlineApp = await launch({ PRAMAAN_URL: URL_, PRAMAAN_USER_DATA: userData() });
  try {
    const w = await offlineApp.firstWindow();
    await w.waitForSelector("text=Can't reach Pramaan", { timeout: 30000 });
    assert.match(await w.textContent("#url"), new RegExp(String(port)));
    assert.match(await w.textContent("body"), /सर्वर/); // Hindi line present
    assert.match(w.url(), /^file:/);

    const back = await listen(appHandler, port); // the server comes back
    await w.click("#retry");
    await w.waitForURL(`${URL_}/`, { timeout: 30000 });
    assert.equal(await w.title(), "Pramaan test home");
    back.s.close();
  } finally {
    await offlineApp.close();
  }
});

app.s.close();
foreign.s.close();
for (const d of dirs) rmSync(d, { recursive: true, force: true });
console.log(`\n${passed} checks passed.`);
process.exit(0);
