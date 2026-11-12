// The browser side of view specs (AGT-10, tier T2). A view is DATA: this interpreter draws it from a fixed set of components and refuses anything else.
// It re-applies the server rules (backend/app/services/viewspec.py), so a spec that somehow got past the server still cannot make the page run anything.
export const ALLOWED_ENDPOINTS = ["/v1/stats/map", "/v1/stats", "/v1/transparency", "/v1/graph", "/v1/profiles"] as const;
export const COMPONENTS = ["heading", "text", "stat", "bar_chart", "table", "list"] as const;
const PATH = /^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$/;
const BAD_KEYS = new Set(["__proto__", "constructor", "prototype"]);
const MARKUP = /[<>]|javascript:|on\w+\s*=/i;
const LINK = /(https?:|www\.|\/\/|\bmailto:)/i;

export interface Bind { endpoint: string; path?: string }
export type Block =
  | { type: "heading"; text: string; level?: 1 | 2 | 3 }
  | { type: "text"; text: string }
  | { type: "stat"; label: string; bind: Bind }
  | { type: "bar_chart"; label: string; bind: Bind }
  | { type: "table"; columns: string[]; bind: Bind }
  | { type: "list"; label: string; bind: Bind };
export interface ViewSpec { title: string; layout?: "stack" | "grid2" | "grid3"; blocks: Block[] }

/** Follow a dotted key path through fetched data. Own properties only; anything odd gives undefined, never an exception. */
export function resolvePath(data: unknown, path: string | undefined): unknown {
  if (!path) return data;
  if (!PATH.test(path)) return undefined;
  let cur: unknown = data;
  for (const key of path.split(".")) {
    if (BAD_KEYS.has(key) || cur === null || typeof cur !== "object" || !Object.prototype.hasOwnProperty.call(cur, key)) return undefined;
    cur = (cur as Record<string, unknown>)[key];
  }
  return cur;
}

export function bindIsAllowed(b: Bind | undefined): boolean {
  return !!b && (ALLOWED_ENDPOINTS as readonly string[]).includes(b.endpoint) && (!b.path || (PATH.test(b.path) && !b.path.split(".").some((k) => BAD_KEYS.has(k))));
}

/** Only blocks that pass every rule are drawn; the rest are dropped silently. */
export function safeBlocks(spec: unknown): Block[] {
  const blocks = (spec as { blocks?: unknown })?.blocks;
  if (!Array.isArray(blocks)) return [];
  return blocks.slice(0, 20).filter((b): b is Block => {
    if (!b || typeof b !== "object" || !(COMPONENTS as readonly string[]).includes((b as { type: string }).type)) return false;
    const texts = [(b as { text?: string }).text, (b as { label?: string }).label, ...(((b as { columns?: string[] }).columns) ?? [])].filter((t): t is string => typeof t === "string");
    if (texts.some((t) => t.length > 600 || MARKUP.test(t) || LINK.test(t))) return false;
    if ("bind" in (b as object) && !bindIsAllowed((b as { bind?: Bind }).bind)) return false;
    return true;
  });
}

export function asEntries(v: unknown): [string, number | string][] {
  if (v && typeof v === "object" && !Array.isArray(v)) return Object.entries(v as Record<string, unknown>).filter(([, x]) => typeof x === "number" || typeof x === "string") as [string, number | string][];
  if (Array.isArray(v)) return v.map((x, i) => [String(i + 1), typeof x === "object" ? JSON.stringify(x).slice(0, 80) : String(x)] as [string, string]);
  return [];
}
