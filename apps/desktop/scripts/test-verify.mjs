// Offline verifier checks. The fixture was signed by the BACKEND's Python signer (scripts/fixtures), so this proves the
// two implementations agree on canonical JSON, hashing and Ed25519, including non-ASCII text and JSON-special characters.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { verifyCertificate, canonicalJson } = require("../src/verify.js");
const load = (f) => JSON.parse(readFileSync(new URL(`./fixtures/${f}`, import.meta.url), "utf8"));
const cert = load("cert.json");
const keys = load("keys.json");
const clone = () => structuredClone(cert);
let n = 0;
const check = (name, fn) => { fn(); n++; console.log(`• ${name} … ok`); };

check("a certificate signed by the Python backend verifies", () => {
  const r = verifyCertificate(cert, keys);
  assert.equal(r.valid, true, r.reason);
  assert.equal(r.certId, "PRM-TESTVECTOR");
});
check("canonical JSON matches the server (sorted keys, raw UTF-8)", () => {
  assert.equal(canonicalJson({ b: 1, a: "é", c: [true, null] }), '{"a":"é","b":1,"c":[true,null]}');
});
check("editing a claim breaks it", () => {
  const c = clone(); c.payload.claims[0].value = "Padma Vibhushan";
  assert.equal(verifyCertificate(c, keys).valid, false);
});
check("editing the name breaks it", () => {
  const c = clone(); c.payload.full_name = "Someone Else";
  assert.equal(verifyCertificate(c, keys).valid, false);
});
check("recomputing the digest after editing still fails (signature does not match)", () => {
  const c = clone(); c.payload.full_name = "Someone Else";
  c.digest = undefined;
  const r = verifyCertificate(c, keys);
  assert.equal(r.valid, false); assert.equal(r.code, "bad_signature");
});
check("a corrupted signature fails", () => {
  const c = clone(); c.signature = c.signature.slice(0, -2) + "AA";
  assert.equal(verifyCertificate(c, keys).valid, false);
});
check("an unknown key id is refused, never trusted from the file", () => {
  const r = verifyCertificate(cert, {});
  assert.equal(r.valid, false); assert.equal(r.code, "unknown_key");
});
check("a key swapped under the same id is refused", () => {
  const evil = { [cert.key_id]: Buffer.alloc(32, 7).toString("base64url") };
  assert.equal(verifyCertificate(cert, evil).valid, false);
});
check("garbage input does not throw", () => {
  for (const bad of [null, {}, { payload: {} }, "x", 5]) assert.equal(verifyCertificate(bad, keys).valid, false);
});
console.log(`\n${n} checks passed.`);
