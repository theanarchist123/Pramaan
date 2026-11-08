/**
 * Pramaan TypeScript SDK — zero dependencies (uses the platform `fetch` and Web Crypto).
 * Runs in Node 18+, Deno, Bun, Cloudflare Workers and browsers.
 *
 *   const p = new Pramaan({ baseUrl: "https://your-host" });
 *   const v = await p.verify("PRM-ABCDEFGHJK");
 *
 * Request/response shapes for every endpoint are generated from the server's OpenAPI document
 * into `./schema.d.ts` (`npm run generate`); the hand-written types below cover the common calls.
 */
export type { paths, components } from "./schema";

export interface VerifyResult {
  valid: boolean;
  code: string;
  reason: string;
  revoked: boolean;
  digest: string;
  key_id: string;
  issued_at: string;
  chain_ok: boolean;
  signature_ok: boolean;
  signature: string;
  public_key: string;
  log_position: number | null;
  log_size: number;
  changed_fields: string[];
  payload: { full_name: string; claims: { field: string; value: string; status: string }[] } | null;
}

export interface SearchHit {
  id: string;
  slug: string;
  full_name: string;
  headline: string;
  sector: string;
  state: string;
  score: number;
  reasons: string[];
  claims: { value: string; status: string }[];
}

export interface SearchResponse {
  query: string;
  plan: { state: string | null; sector: string | null; semantic_query: string };
  relaxed: boolean;
  results: SearchHit[];
}

export interface PramaanOptions {
  apiKey?: string;
  token?: string;
  baseUrl?: string;
  fetch?: typeof fetch;
}

export class PramaanError extends Error {
  constructor(public status: number, public detail: string, public retryAfter?: number) {
    super(`${status}: ${detail}`);
    this.name = status === 429 ? "RateLimited" : "PramaanError";
  }
}

type Json = Record<string, unknown>;

export class Pramaan {
  readonly baseUrl: string;
  private headers: Record<string, string>;
  private f: typeof fetch;

  constructor(opts: PramaanOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? "http://localhost:8000").replace(/\/$/, "");
    this.headers = {};
    if (opts.apiKey) this.headers["X-API-Key"] = opts.apiKey;
    else if (opts.token) this.headers["Authorization"] = `Bearer ${opts.token}`;
    this.f = opts.fetch ?? fetch.bind(globalThis);
  }

  private async req<T>(method: string, path: string, opts: { params?: Json; json?: unknown; raw?: boolean } = {}): Promise<T> {
    const url = new URL(this.baseUrl + path);
    for (const [k, v] of Object.entries(opts.params ?? {})) if (v != null) url.searchParams.set(k, String(v));
    const res = await this.f(url, {
      method,
      headers: { ...this.headers, ...(opts.json !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: opts.json !== undefined ? JSON.stringify(opts.json) : undefined,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const detail = typeof body?.detail === "string" ? body.detail : res.statusText;
      throw new PramaanError(res.status, detail, res.status === 429 ? Number(res.headers.get("retry-after") ?? 60) : undefined);
    }
    if (res.status === 204) return undefined as T;
    return (opts.raw ? await res.arrayBuffer() : await res.json()) as T;
  }

  // ---- public (no key needed) -------------------------------------------------------
  verify(code: string) {
    return this.req<VerifyResult>("GET", `/v1/verify/${code.trim().toUpperCase()}`);
  }
  /** Would this possibly-edited content still match the signature? `changed_fields` names what was altered. */
  checkPayload(code: string, payload: Json) {
    return this.req<VerifyResult>("POST", "/v1/verify/check", { json: { code, payload } });
  }
  certificate(code: string) {
    return this.req<Json>("GET", `/v1/certificates/${code.trim().toUpperCase()}`);
  }
  /** Plain-English search in any language. Each hit explains why it matched. */
  search(query: string, o: { state?: string; sector?: string; limit?: number } = {}) {
    return this.req<SearchResponse>("POST", "/v1/search", { json: { query, limit: 12, ...o } });
  }
  profile(slug: string) {
    return this.req<Json>("GET", `/v1/profiles/${slug}`);
  }
  listProfiles(o: { q?: string; sector?: string; state?: string; limit?: number; offset?: number } = {}) {
    return this.req<Json[]>("GET", "/v1/profiles", { params: o });
  }
  graph() {
    return this.req<{ nodes: Json[]; links: Json[] }>("GET", "/v1/graph");
  }
  mapStats() {
    return this.req<Json>("GET", "/v1/stats/map");
  }
  transparencyOk() {
    return this.req<{ ok: boolean; entries: number }>("GET", "/v1/transparency/verify");
  }
  publicKeys() {
    return this.req<{ keys: Json[] }>("GET", "/.well-known/pramaan-keys.json");
  }
  /** URL of a live "Verified by Pramaan" SVG badge for use in <img src>. */
  badgeUrl(code: string) {
    return `${this.baseUrl}/v1/badge/certificate/${code.trim().toUpperCase()}.svg`;
  }
  certificatePdf(code: string) {
    return this.req<ArrayBuffer>("GET", `/v1/certificates/${code.trim().toUpperCase()}/pdf`, { raw: true });
  }

  // ---- authenticated ----------------------------------------------------------------
  myProfiles() {
    return this.req<Json[]>("GET", "/v1/profiles/mine");
  }
  /** The response includes the signing `secret` — shown only once. */
  createWebhook(url: string, events: string[]) {
    return this.req<{ id: string; secret: string } & Json>("POST", "/v1/webhooks", { json: { url, events } });
  }
  listWebhooks() {
    return this.req<Json[]>("GET", "/v1/webhooks");
  }
  deleteWebhook(id: string) {
    return this.req<void>("DELETE", `/v1/webhooks/${id}`);
  }
  testWebhook(id: string) {
    return this.req<{ ok: boolean; status_code: number | null; error: string }>("POST", `/v1/webhooks/${id}/test`);
  }
}

/**
 * Verify an incoming webhook. Pass the RAW request body (string or bytes), never re-serialised JSON.
 * Rejects tampered bodies, wrong secrets and replays older than `toleranceSeconds`.
 */
export async function verifyWebhook(
  secret: string,
  signatureHeader: string,
  body: string | Uint8Array,
  toleranceSeconds = 300,
): Promise<boolean> {
  try {
    const parts = Object.fromEntries(signatureHeader.split(",").map((p) => p.split("=", 2) as [string, string]));
    const ts = Number(parts.t);
    if (!Number.isFinite(ts) || Math.abs(Date.now() / 1000 - ts) > toleranceSeconds) return false;
    const enc = new TextEncoder();
    const bodyBytes = typeof body === "string" ? enc.encode(body) : body;
    const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    const msg = new Uint8Array([...enc.encode(`${ts}.`), ...bodyBytes]);
    const mac = new Uint8Array(await crypto.subtle.sign("HMAC", key, msg));
    const expected = [...mac].map((b) => b.toString(16).padStart(2, "0")).join("");
    const given = parts.v1 ?? "";
    if (given.length !== expected.length) return false;
    let diff = 0; // constant-time compare
    for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ given.charCodeAt(i);
    return diff === 0;
  } catch {
    return false;
  }
}
