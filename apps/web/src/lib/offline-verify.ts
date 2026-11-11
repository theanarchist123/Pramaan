// Check a certificate file ON THIS DEVICE (no certificate content leaves the browser). Same algorithm as the server and the
// desktop app: canonical JSON -> SHA-256 -> Ed25519 signature, against a registry key fetched from /.well-known.
// Needs WebCrypto Ed25519 (current Chrome, Firefox and Safari); otherwise we say so instead of guessing.
import { API_URL } from "@/lib/api";

export type OfflineOutcome =
  | { kind: "valid"; subject: string; certId: string; issuedAt: string }
  | { kind: "altered" | "unknown_key" | "malformed" | "unsupported"; reason: string };

export function canonicalJson(v: unknown): string {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return `[${v.map(canonicalJson).join(",")}]`;
  const o = v as Record<string, unknown>;
  return `{${Object.keys(o).sort().map((k) => `${JSON.stringify(k)}:${canonicalJson(o[k])}`).join(",")}}`;
}

const b64url = (s: string) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "=")), (c) => c.charCodeAt(0));
const hex = (buf: ArrayBuffer) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const fromHex = (h: string) => Uint8Array.from(h.match(/.{2}/g)!.map((b) => parseInt(b, 16)));

export async function checkCertificateFile(text: string): Promise<OfflineOutcome> {
  let cert: { payload?: Record<string, unknown>; signature?: string; key_id?: string; digest?: string };
  try {
    cert = JSON.parse(text);
  } catch {
    return { kind: "malformed", reason: "That file is not JSON." };
  }
  if (!cert?.payload || !cert.signature) return { kind: "malformed", reason: "That is not a Pramaan certificate file (no payload or signature)." };
  if (!globalThis.crypto?.subtle) return { kind: "unsupported", reason: "This browser cannot do the check. Use the Pramaan desktop app instead." };

  const digestBytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalJson(cert.payload)));
  const digest = hex(digestBytes);
  if (cert.digest && cert.digest !== digest) return { kind: "altered", reason: "The content does not match its recorded fingerprint: it was edited." };

  // Only keys the REGISTRY publishes are trusted, never a key that merely appears inside the file.
  let keys: { kid: string; x: string }[] = [];
  try {
    keys = ((await (await fetch(`${API_URL}/.well-known/pramaan-keys.json`)).json()) as { keys: { kid: string; x: string }[] }).keys;
  } catch {
    return { kind: "unknown_key", reason: "Could not reach the registry to fetch its public keys. Check your connection and try again." };
  }
  const key = keys.find((k) => k.kid === cert.key_id);
  if (!key) return { kind: "unknown_key", reason: `The signing key ${cert.key_id ?? "(none)"} is not one the registry publishes.` };
  try {
    const pub = await crypto.subtle.importKey("raw", b64url(key.x), { name: "Ed25519" }, false, ["verify"]);
    const ok = await crypto.subtle.verify({ name: "Ed25519" }, pub, b64url(cert.signature), fromHex(digest));
    if (!ok) return { kind: "altered", reason: "The signature does not match this content: it was edited after issuance." };
  } catch {
    return { kind: "unsupported", reason: "This browser does not support Ed25519 yet. Use the Pramaan desktop app, or a current Chrome, Firefox or Safari." };
  }
  return { kind: "valid", subject: String(cert.payload.full_name ?? ""), certId: String(cert.payload.cert_id ?? ""), issuedAt: String(cert.payload.issued_at ?? "") };
}
