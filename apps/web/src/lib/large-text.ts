const LARGE_KEY = "pramaan.largeText";

/** Toggle the larger-text accessibility mode on <html> and remember it (per viewer, so storage failures are ignored). */
export function toggleLargeText(): boolean {
  const el = document.documentElement;
  const next = el.dataset.largeText !== "true";
  el.dataset.largeText = String(next);
  try {
    localStorage.setItem(LARGE_KEY, String(next));
  } catch {
    /* per-viewer convenience only */
  }
  return next;
}

/** Apply the remembered setting on load; returns whether larger text is on. */
export function restoreLargeText(): boolean {
  try {
    if (localStorage.getItem(LARGE_KEY) === "true") {
      document.documentElement.dataset.largeText = "true";
      return true;
    }
  } catch {
    /* ignore */
  }
  return false;
}
