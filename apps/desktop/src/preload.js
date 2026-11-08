"use strict";
// The ONLY bridge between the web page and the desktop shell. contextIsolation is on and Node is not
// exposed to the page: it can learn that it is inside the desktop app, and ask to retry after offline.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("pramaanDesktop", {
  isDesktop: true,
  platform: process.platform,
  retry: () => ipcRenderer.send("pramaan:retry"),
});
