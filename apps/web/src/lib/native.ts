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
