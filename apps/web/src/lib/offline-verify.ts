// Check a certificate file ON THIS DEVICE (no certificate content leaves the browser). The algorithm lives in @pramaan/verify, the same
// package the desktop app and third parties use: canonical JSON -> SHA-256 -> Ed25519, against registry keys fetched from /.well-known.
import { verifyCertificate } from "@pramaan/verify";
import { API_URL } from "@/lib/api";

export type OfflineOutcome =
  | { kind: "valid"; subject: string; certId: string; issuedAt: string }
  | { kind: "altered" | "unknown_key" | "malformed" | "unsupported"; reason: string };

export { canonicalJson } from "@pramaan/verify";

export async function checkCertificateFile(text: string): Promise<OfflineOutcome> {
  let cert: unknown;
  try {
    cert = JSON.parse(text);
  } catch {
    return { kind: "malformed", reason: "That file is not JSON." };
  }
  if (!globalThis.crypto?.subtle) return { kind: "unsupported", reason: "This browser cannot do the check. Use the Pramaan desktop app instead." };

  // Only keys the REGISTRY publishes are trusted, never a key that merely appears inside the file.
  let keys: Record<string, string> = {};
  try {
    const published = (await (await fetch(`${API_URL}/.well-known/pramaan-keys.json`)).json()) as { keys: { kid: string; x: string }[] };
    keys = Object.fromEntries(published.keys.map((k) => [k.kid, k.x]));
  } catch {
    return { kind: "unknown_key", reason: "Could not reach the registry to fetch its public keys. Check your connection and try again." };
  }

  const r = await verifyCertificate(cert, keys);
  if (r.valid) return { kind: "valid", subject: String(r.subject ?? ""), certId: String(r.certId ?? ""), issuedAt: String(r.issuedAt ?? "") };
  switch (r.code) {
    case "tampered":
    case "bad_signature":
      return { kind: "altered", reason: r.reason };
    case "unknown_key":
    case "key_mismatch":
      return { kind: "unknown_key", reason: r.reason };
    case "unsupported":
      return { kind: "unsupported", reason: r.reason };
    default:
      return { kind: "malformed", reason: r.reason };
  }
}
