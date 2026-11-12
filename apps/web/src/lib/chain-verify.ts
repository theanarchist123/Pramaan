export interface LogEntry {
  id: number;
  certificate_code: string;
  digest: string;
  prev_hash: string;
  entry_hash: string;
  issued_at: string;
}

export const GENESIS = "0".repeat(64);

async function sha256Hex(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export interface ChainResult {
  ok: boolean;
  /** index (in the oldest-first list) of the first entry that does not check out */
  badIndex: number | null;
  why: "" | "link" | "hash";
  /** true when the first entry points at the genesis value, so the whole log from the start was covered */
  fromStart: boolean;
}

/**
 * Re-computes the chain on this device, the same rule the registry uses: entry_hash = SHA-256(prev_hash | digest | issued_at), and
 * each entry's prev_hash is the entry before it. `entries` must be oldest first. This trusts nothing the server concluded.
 */
export async function verifyChainInBrowser(entries: LogEntry[]): Promise<ChainResult> {
  let prev: string | null = null;
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    if (prev !== null && e.prev_hash !== prev) return { ok: false, badIndex: i, why: "link", fromStart: false };
    if ((await sha256Hex(`${e.prev_hash}|${e.digest}|${e.issued_at}`)) !== e.entry_hash) return { ok: false, badIndex: i, why: "hash", fromStart: false };
    prev = e.entry_hash;
  }
  return { ok: true, badIndex: null, why: "", fromStart: entries.length > 0 && entries[0].prev_hash === GENESIS };
}
