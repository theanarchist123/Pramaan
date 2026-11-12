// @pramaan/verify: check a Pramaan certificate and the public log on the viewer's own device. No dependencies, no network calls:
// the caller supplies the registry's public keys. Uses WebCrypto (browsers, Node 20+, Deno, Bun), so the same code runs in the web
// app, the desktop app and a third party's page. Mirrors backend/app/core/signing.py and backend/app/core/merkle.py exactly; the
// tests run it against vectors produced by that Python code.

const enc = new TextEncoder();
const subtle = () => {
  const s = globalThis.crypto?.subtle;
  if (!s) throw new Error("WebCrypto is not available in this environment");
  return s;
};

const toHex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
export const fromHex = (h) => Uint8Array.from(h.match(/.{2}/g) ?? [], (b) => parseInt(b, 16));
export function fromB64Url(s) {
  const b = s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "=");
  return Uint8Array.from(atob(b), (c) => c.charCodeAt(0));
}
const sha256 = async (bytes) => new Uint8Array(await subtle().digest("SHA-256", bytes));

/** Deterministic JSON identical to the registry's: sorted keys, no whitespace, raw UTF-8. */
export function canonicalJson(v) {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return `[${v.map(canonicalJson).join(",")}]`;
  return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${canonicalJson(v[k])}`).join(",")}}`;
}

export async function digestOf(payload) {
  return toHex(await sha256(enc.encode(canonicalJson(payload))));
}

/** A key's id is derived from the key itself, so a key cannot be swapped in under someone else's id. */
export async function keyId(publicKeyB64Url) {
  return toHex(await sha256(fromB64Url(publicKeyB64Url))).slice(0, 16);
}

/** Ed25519 check. Returns false for anything wrong; throws "unsupported" only when this runtime cannot do Ed25519 at all. */
export async function verifySignature(digestHex, signatureB64Url, publicKeyB64Url) {
  let key;
  try {
    key = await subtle().importKey("raw", fromB64Url(publicKeyB64Url), { name: "Ed25519" }, false, ["verify"]);
  } catch (e) {
    if (e?.name === "NotSupportedError") throw new Error("unsupported");
    return false;
  }
  try {
    return await subtle().verify({ name: "Ed25519" }, key, fromB64Url(signatureB64Url), fromHex(digestHex));
  } catch {
    return false;
  }
}

/**
 * cert: the certificate JSON ({payload, signature, key_id, digest?}). keys: { [kid]: publicKeyB64Url } as published by the registry
 * (/.well-known/pramaan-keys.json) or pinned by the app. Only keys you pass in are trusted: a key inside the file proves nothing.
 * Returns { valid, code, reason, ... }; code is one of ok | malformed | tampered | unknown_key | key_mismatch | bad_signature | unsupported.
 */
export async function verifyCertificate(cert, keys) {
  if (!cert || typeof cert !== "object" || !cert.payload || !cert.signature) {
    return { valid: false, code: "malformed", reason: "This file is not a Pramaan certificate (no payload or signature)." };
  }
  const digest = await digestOf(cert.payload);
  if (cert.digest && cert.digest !== digest) {
    return { valid: false, code: "tampered", digest, reason: "The content does not match its recorded fingerprint: it was edited." };
  }
  const pub = keys && cert.key_id ? keys[cert.key_id] : undefined;
  if (!pub) {
    return { valid: false, code: "unknown_key", digest, reason: `The signing key ${cert.key_id || "(none)"} is not one you trust or the registry publishes.` };
  }
  if ((await keyId(pub)) !== cert.key_id) {
    return { valid: false, code: "key_mismatch", digest, reason: "The key you hold does not match the key id on the certificate." };
  }
  let ok;
  try {
    ok = await verifySignature(digest, cert.signature, pub);
  } catch {
    return { valid: false, code: "unsupported", digest, reason: "This environment does not support Ed25519 yet. Use a current browser, or the Pramaan desktop app." };
  }
  if (!ok) return { valid: false, code: "bad_signature", digest, reason: "The signature does not match this content: it was edited after issuance." };
  const p = cert.payload;
  return {
    valid: true, code: "ok", digest, reason: "Signature valid; content unchanged since issuance.",
    subject: p.full_name, certId: p.cert_id, issuedAt: p.issued_at, claims: (p.claims || []).length,
    note: "Checked on this device. This does not show whether the registry has since revoked the certificate; check it online for that.",
  };
}

// ----------------------------------------------------------------------------------------------- the public log (RFC 6962 / 9162)
const cat = (...parts) => {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
};
const nodeHash = (l, r) => sha256(cat(Uint8Array.of(1), l, r));
export const leafHash = (entryBytes) => sha256(cat(Uint8Array.of(0), entryBytes));
const eq = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

/** Is `leaf` (a leaf hash, bytes) the `index`-th of `size` leaves under `root`? proof: array of byte arrays. */
export async function verifyInclusion(leaf, index, size, proof, root) {
  if (!(index >= 0 && index < size)) return false;
  let fn = index, sn = size - 1, r = leaf;
  for (const p of proof) {
    if (sn === 0) return false;
    if (fn & 1 || fn === sn) {
      r = await nodeHash(p, r);
      if (!(fn & 1)) while (!(fn & 1) && fn !== 0) { fn >>= 1; sn >>= 1; }
    } else {
      r = await nodeHash(r, p);
    }
    fn >>= 1; sn >>= 1;
  }
  return sn === 0 && eq(r, root);
}

/** Is the tree of size `first` (root firstRoot) a prefix of the tree of size `second` (root secondRoot)? */
export async function verifyConsistency(first, second, firstRoot, secondRoot, proof) {
  if (!(first > 0 && first <= second)) return false;
  if (first === second) return proof.length === 0 && eq(firstRoot, secondRoot);
  const path = [...proof];
  if ((first & (first - 1)) === 0) path.unshift(firstRoot);
  if (path.length === 0) return false;
  let fn = first - 1, sn = second - 1;
  while (fn & 1) { fn >>= 1; sn >>= 1; }
  let fr = path[0], sr = path[0];
  for (const c of path.slice(1)) {
    if (sn === 0) return false;
    if (fn & 1 || fn === sn) {
      fr = await nodeHash(c, fr); sr = await nodeHash(c, sr);
      if (!(fn & 1)) while (!(fn & 1) && fn !== 0) { fn >>= 1; sn >>= 1; }
    } else {
      sr = await nodeHash(sr, c);
    }
    fn >>= 1; sn >>= 1;
  }
  return eq(fr, firstRoot) && eq(sr, secondRoot) && sn === 0;
}

/** The registry's signed checkpoint: { text, signature, key_id }. Checks the signature and that `text` says what is claimed. */
export async function verifyCheckpoint(cp, keys) {
  const pub = keys?.[cp?.key_id];
  if (!pub) return { valid: false, reason: "The checkpoint was signed with a key you do not trust." };
  if ((await keyId(pub)) !== cp.key_id) return { valid: false, reason: "The key does not match the key id." };
  const m = /^pramaan-log-checkpoint-v1\nsize=(\d+)\nroot=([0-9a-f]{64})\n$/.exec(cp.text ?? "");
  if (!m) return { valid: false, reason: "That is not a Pramaan log checkpoint." };
  const digest = toHex(await sha256(enc.encode(cp.text)));
  let ok = false;
  try { ok = await verifySignature(digest, cp.signature, pub); } catch { return { valid: false, reason: "This environment does not support Ed25519 yet." }; }
  return ok ? { valid: true, size: Number(m[1]), root: m[2] } : { valid: false, reason: "The checkpoint signature does not match." };
}
