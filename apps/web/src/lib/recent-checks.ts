// Recent checks stay on THIS device only (localStorage; a convenience, the page works without it) and can be cleared.
const KEY = "pramaan.recentChecks";
export interface RecentCheck { code: string; name: string; at: string }

export function readRecent(): RecentCheck[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v.slice(0, 6) : [];
  } catch {
    return [];
  }
}
export function rememberCheck(c: RecentCheck) {
  try {
    const rest = readRecent().filter((r) => r.code !== c.code);
    localStorage.setItem(KEY, JSON.stringify([c, ...rest].slice(0, 6)));
  } catch {
    /* storage blocked */
  }
}
export function clearRecent() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
