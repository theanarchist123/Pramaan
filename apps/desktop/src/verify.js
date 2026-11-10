"use strict";
// Offline certificate verification. Nothing here touches the network: it re-computes the digest of the signed payload
// and checks the Ed25519 signature against a public key the app cached earlier (from /.well-known/pramaan-keys.json).
// This is the same check the server performs (backend/app/core/signing.py), written with Node's own crypto.

const crypto = require("node:crypto");

// DER prefix that wraps a raw 32-byte Ed25519 public key into an X.509 SubjectPublicKeyInfo.
const SPKI_ED25519_PREFIX = Buffer.from("302a300506032b6570032100", "hex");

/** Deterministic JSON identical to the server's: sorted keys, no whitespace, UTF-8 (no \uXXXX for non-ASCII). */
function canonicalJson(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(value[k])}`).join(",")}}`;
}

function digestOf(payload) {
  return crypto.createHash("sha256").update(canonicalJson(payload), "utf8").digest("hex");
}

function keyId(publicKeyB64) {
  return crypto.createHash("sha256").update(Buffer.from(publicKeyB64, "base64url")).digest("hex").slice(0, 16);
}

function verifySignature(digestHex, signatureB64, publicKeyB64) {
  try {
    const raw = Buffer.from(publicKeyB64, "base64url");
    if (raw.length !== 32) return false;
    const key = crypto.createPublicKey({ key: Buffer.concat([SPKI_ED25519_PREFIX, raw]), format: "der", type: "spki" });
    return crypto.verify(null, Buffer.from(digestHex, "hex"), key, Buffer.from(signatureB64, "base64url"));
  } catch {
    return false;
  }
}

/**
 * cert: the JSON the API returns for a certificate ({payload, signature, key_id, digest?, ...}).
 * keys: { [kid]: publicKeyB64 } cached from the registry. Only cached keys are trusted; a key that merely appears
 * inside the file proves nothing (an attacker could ship their own).
 */
function verifyCertificate(cert, keys) {
  if (!cert || typeof cert !== "object" || !cert.payload || !cert.signature) {
    return { valid: false, code: "malformed", reason: "This file is not a Pramaan certificate (no payload or signature)." };
  }
  const digest = digestOf(cert.payload);
  if (cert.digest && cert.digest !== digest) {
    return { valid: false, code: "tampered", reason: "The certificate content does not match its recorded digest: it was edited.", digest };
  }
  const pub = keys && cert.key_id ? keys[cert.key_id] : undefined;
  if (!pub) {
    return {
      valid: false, code: "unknown_key", digest,
      reason: `The signing key ${cert.key_id || "(none)"} is not in this app's cached registry keys. Connect to the internet once so the app can refresh them.`,
    };
  }
  if (keyId(pub) !== cert.key_id) {
    return { valid: false, code: "key_mismatch", digest, reason: "The cached key does not match the key id on the certificate." };
  }
  if (!verifySignature(digest, cert.signature, pub)) {
    return { valid: false, code: "bad_signature", digest, reason: "The signature does not match this content: it was edited after issuance." };
  }
  const p = cert.payload;
  return {
    valid: true, code: "ok", digest,
    reason: "Signature valid; content unchanged since issuance.",
    subject: p.full_name, certId: p.cert_id, issuedAt: p.issued_at, claims: (p.claims || []).length,
    note: "Checked offline. This does not show whether the registry has since revoked the certificate; open it online for that.",
  };
}

module.exports = { canonicalJson, digestOf, keyId, verifySignature, verifyCertificate };
