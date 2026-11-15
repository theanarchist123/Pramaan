/**
 * Small bridge to the Android app shell (Capacitor). In a normal browser every function is a harmless no-op, so the same code runs on the web, the installed web app and the Android app.
 * The shell injects `window.Capacitor` into the page it loads, so nothing from Capacitor is bundled into the website.
 */
type Plugin = Record<string, (arg?: unknown) => Promise<unknown>>;
interface CapacitorGlobal {
  isNativePlatform?: () => boolean;
  Plugins?: Record<string, Plugin | undefined>;
}

function cap(): CapacitorGlobal | null {
  if (typeof window === "undefined") return null;
  return (window as unknown as { Capacitor?: CapacitorGlobal }).Capacitor ?? null;
}

/** True only inside the Android app. */
export function isNativeApp(): boolean {
  try {
    return cap()?.isNativePlatform?.() === true;
  } catch {
    return false;
  }
}

/** A short tap-like buzz. `kind` maps to the platform's standard impact strengths. Never throws; does nothing in a browser or when the viewer reduces motion. */
export function haptic(kind: "light" | "medium" | "heavy" | "success" = "light"): void {
  if (!isNativeApp()) return;
  try {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const h = cap()?.Plugins?.Haptics;
    if (!h) return;
    if (kind === "success") void h.notification?.({ type: "SUCCESS" }).catch(() => {});
    else void h.impact?.({ style: kind.toUpperCase() }).catch(() => {});
  } catch {
    /* a missing plugin must never break the screen */
  }
}

function toHex(rgb: string): string | null {
  const m = rgb.match(/\d+(\.\d+)?/g);
  if (!m || m.length < 3) return null;
  return "#" + m.slice(0, 3).map((x) => Math.round(Number(x)).toString(16).padStart(2, "0")).join("");
}

/** Make the Android status bar match the top app bar (its colour and light/dark icons) so the two read as one piece. Does nothing in a browser or if the plugin is absent. */
export function syncSystemBars(dark: boolean): void {
  if (!isNativeApp()) return;
  try {
    const bar = cap()?.Plugins?.StatusBar;
    if (!bar) return;
    const hex = toHex(getComputedStyle(document.body).backgroundColor);
    if (hex) void bar.setBackgroundColor?.({ color: hex }).catch(() => {});
    void bar.setStyle?.({ style: dark ? "DARK" : "LIGHT" }).catch(() => {}); // DARK = light icons for a dark bar; LIGHT = dark icons for a light bar
  } catch {
    /* never break the screen */
  }
}
