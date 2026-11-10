"use strict";
const { app, BrowserWindow, Menu, Tray, globalShortcut, shell, ipcMain, nativeImage, session } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { PROTOCOL, resolveDeepLink, findDeepLink } = require("./links");
const { startAutoUpdates } = require("./updater");

const TEST = process.env.PRAMAAN_TEST === "1";
if (process.env.PRAMAAN_USER_DATA) app.setPath("userData", process.env.PRAMAAN_USER_DATA);

function configuredUrl() {
  if (process.env.PRAMAAN_URL) return process.env.PRAMAAN_URL;
  // A config.json lets an organisation point the app at its own server. Checked in order: the user's data folder
  // (survives auto-updates, which replace the install folder), beside the executable, then the bundled default.
  const candidates = [
    path.join(app.getPath("userData"), "config.json"),
    path.join(path.dirname(process.execPath), "config.json"),
    process.resourcesPath ? path.join(process.resourcesPath, "config.json") : "",
  ].filter(Boolean);
  for (const file of candidates) {
    try {
      const cfg = JSON.parse(fs.readFileSync(file, "utf8"));
      if (typeof cfg.url === "string") return cfg.url;
    } catch {
      /* not there: try the next */
    }
  }
  return "http://localhost:3100";
}
const APP_URL = configuredUrl().replace(/\/$/, "");
const ORIGIN = new URL(APP_URL).origin;

let win = null;
let tray = null;
let quitting = false;
let pendingLink = null;

const boundsFile = () => path.join(app.getPath("userData"), "window.json");
function loadBounds() {
  try {
    const b = JSON.parse(fs.readFileSync(boundsFile(), "utf8"));
    if ([b.width, b.height].every((n) => Number.isFinite(n) && n >= 600)) return b;
  } catch {
    /* first run */
  }
  return { width: 1280, height: 860 };
}
function saveBounds() {
  if (!win || win.isMinimized() || win.isMaximized()) return;
  try {
    fs.writeFileSync(boundsFile(), JSON.stringify(win.getBounds()));
  } catch {
    /* not important */
  }
}

const isWebUrl = (u) => /^https?:\/\//i.test(u);
function openExternally(url) {
  if (isWebUrl(url)) shell.openExternal(url); // browsers only: never file:, never custom schemes
}

function showWindow() {
  if (!win) return;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
}

function navigate(pathname) {
  if (!win) return;
  win.loadURL(ORIGIN + pathname);
  showWindow();
}

function handleDeepLink(raw) {
  const target = resolveDeepLink(raw);
  if (!target) return; // anything we don't recognise is ignored
  if (win) navigate(target);
  else pendingLink = target;
}

function createWindow() {
  const icon = path.join(__dirname, "..", "assets", "icon.png");
  win = new BrowserWindow({
    ...loadBounds(),
    minWidth: 380,
    minHeight: 560,
    show: false,
    title: "Pramaan",
    icon,
    backgroundColor: "#f8f4ec",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webviewTag: false,
      spellcheck: true,
    },
  });
  win.once("ready-to-show", () => win.show());
  win.on("resize", saveBounds);
  win.on("move", saveBounds);
  win.on("close", (e) => {
    // Closing the window keeps the app in the tray (so the global shortcut and deep links keep working).
    if (!quitting && tray && !TEST) {
      e.preventDefault();
      win.hide();
    }
  });

  // --- lock the window to our own origin -------------------------------------------------------
  win.webContents.setWindowOpenHandler(({ url }) => {
    let target;
    try {
      target = new URL(url, ORIGIN);
    } catch {
      return { action: "deny" };
    }
    if (target.origin !== ORIGIN) openExternally(target.href);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    let target;
    try {
      target = new URL(url);
    } catch {
      return event.preventDefault();
    }
    if (target.origin === ORIGIN) return;
    event.preventDefault();
    openExternally(url);
  });
  win.webContents.on("will-attach-webview", (event) => event.preventDefault());

  // --- offline / server down ---------------------------------------------------------------------
  win.webContents.on("did-fail-load", (_e, code, _desc, _url, isMainFrame) => {
    if (!isMainFrame || code === -3 /* aborted by a newer navigation */) return;
    win.loadFile(path.join(__dirname, "offline.html"), { query: { url: APP_URL } });
  });

  win.loadURL(pendingLink ? ORIGIN + pendingLink : APP_URL);
  pendingLink = null;
}

function buildTray() {
  const img = nativeImage.createFromPath(path.join(__dirname, "..", "assets", "icon.png")).resize({ width: 18, height: 18 });
  tray = new Tray(img);
  tray.setToolTip("Pramaan");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Open Pramaan", click: showWindow },
      { label: "Verify a certificate", click: () => navigate("/verify") },
      { label: "Search the registry", click: () => navigate("/directory") },
      { type: "separator" },
      { label: "Quit", click: () => app.quit() },
    ]),
  );
  tray.on("click", showWindow);
}

function buildMenu() {
  const template = [
    {
      label: "Pramaan",
      submenu: [
        { label: "Verify a certificate", accelerator: "CmdOrCtrl+L", click: () => navigate("/verify") },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    { label: "Edit", submenu: [{ role: "undo" }, { role: "redo" }, { type: "separator" }, { role: "cut" }, { role: "copy" }, { role: "paste" }, { role: "selectAll" }] },
    {
      label: "View",
      submenu: [{ role: "reload" }, { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" }, { role: "togglefullscreen" }, ...(app.isPackaged ? [] : [{ role: "toggleDevTools" }])],
    },
    { label: "Window", submenu: [{ role: "minimize" }, { role: "close" }] },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit(); // a second copy hands its deep link to the first, then exits
} else {
  app.on("second-instance", (_event, argv) => {
    showWindow();
    handleDeepLink(findDeepLink(argv));
  });
  app.on("open-url", (event, url) => {
    event.preventDefault(); // macOS delivers deep links here
    handleDeepLink(url);
  });
  app.on("before-quit", () => {
    quitting = true;
  });
  app.on("will-quit", () => globalShortcut.unregisterAll());
  app.on("window-all-closed", () => {
    if (process.platform !== "darwin" && (!tray || TEST)) app.quit();
  });

  app.whenReady().then(() => {
    // Nothing in the app needs camera, location, notifications or the like: deny every request.
    session.defaultSession.setPermissionRequestHandler((_wc, _perm, callback) => callback(false));
    session.defaultSession.setPermissionCheckHandler(() => false);

    // Only the offline screen (a local file) may ask us to retry.
    ipcMain.on("pramaan:retry", (event) => {
      if (event.senderFrame && event.senderFrame.url.startsWith("file:") && win) win.loadURL(APP_URL);
    });

    // Register pramaan:// with the OS only for the real installed app (never in tests: it edits the user's settings).
    if (app.isPackaged && !TEST) app.setAsDefaultProtocolClient(PROTOCOL);
    buildMenu();
    pendingLink = resolveDeepLink(findDeepLink(process.argv));
    createWindow();
    startAutoUpdates(app);
    if (!TEST) {
      buildTray();
      globalShortcut.register("CommandOrControl+Shift+P", () => (win && win.isVisible() && win.isFocused() ? win.hide() : showWindow()));
    }
  });
}
