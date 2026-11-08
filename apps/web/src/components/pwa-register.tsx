"use client";

import { useEffect } from "react";

/** Registers the service worker in production builds only (a worker in `next dev` caches stale code). */
export function PwaRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* the app works fine without it */
    });
  }, []);
  return null;
}
