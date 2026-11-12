import { test } from "node:test";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import {
  canonicalJson, fromHex, keyId, leafHash, verifyCertificate, verifyCheckpoint, verifyConsistency, verifyInclusion,
} from "../src/index.js";

const load = (f) => JSON.parse(readFileSync(new URL(`./fixtures/${f}`, import.meta.url), "utf8"));
const cert = load("cert.json");
const keys = load("keys.json");
const M = load("merkle.json");
const clone = () => structuredClone(cert);
const b = (arr) => arr.map(fromHex);

test("a certificate signed by the Python backend verifies", async () => {
  const r = await verifyCertificate(cert, keys);
  assert.equal(r.valid, true, r.reason);
  assert.equal(r.certId, "PRM-TESTVECTOR");
});
test("canonical JSON matches the registry (sorted keys, raw UTF-8)", () => {
  assert.equal(canonicalJson({ b: 1, a: "é", c: [true, null] }), '{"a":"é","b":1,"c":[true,null]}');
});
test("editing the name, a claim, or the signature breaks it", async () => {
  const a = clone(); a.payload.full_name = "Someone Else";
  const c = clone(); c.payload.claims[0].value = "Padma Vibhushan";
  const d = clone(); d.signature = d.signature.slice(0, -2) + "AA";
  for (const x of [a, c, d]) assert.equal((await verifyCertificate(x, keys)).valid, false);
});
test("recomputing the digest after an edit still fails on the signature", async () => {
  const c = clone(); c.payload.full_name = "Someone Else"; delete c.digest;
  assert.equal((await verifyCertificate(c, keys)).code, "bad_signature");
});
test("only keys the caller trusts count, and a key cannot be swapped under another id", async () => {
  assert.equal((await verifyCertificate(cert, {})).code, "unknown_key");
  const kid = Object.keys(keys)[0];
  const other = { ...keys, [kid]: M.checkpoint.keys[M.checkpoint.key_id] }; // a different, valid Ed25519 key under the same id
  assert.equal((await verifyCertificate(cert, other)).code, "key_mismatch");
  assert.equal((await keyId(keys[kid])), kid);
});
test("junk input is malformed, never an exception", async () => {
  for (const x of [null, {}, { payload: {} }, "x"]) assert.equal((await verifyCertificate(x, keys)).code, "malformed");
});

test("every inclusion proof for every tree size (1..12) from the Python implementation verifies", async () => {
  for (let n = 1; n <= 12; n++) {
    const t = M.trees[String(n)];
    for (let i = 0; i < n; i++) {
      assert.equal(await verifyInclusion(fromHex(M.leaves[i]), i, n, b(t.inclusion[i]), fromHex(t.root)), true, `n=${n} i=${i}`);
    }
  }
});
test("inclusion fails for the wrong leaf, index or root", async () => {
  const t = M.trees["12"];
  const good = b(t.inclusion[5]);
  assert.equal(await verifyInclusion(fromHex(M.leaves[4]), 5, 12, good, fromHex(t.root)), false);
  assert.equal(await verifyInclusion(fromHex(M.leaves[5]), 6, 12, good, fromHex(t.root)), false);
  assert.equal(await verifyInclusion(fromHex(M.leaves[5]), 5, 12, good, fromHex(M.trees["11"].root)), false);
  assert.equal(await verifyInclusion(await leafHash(new TextEncoder().encode("forged")), 5, 12, good, fromHex(t.root)), false);
});
test("every consistency proof between every pair of sizes verifies, and a rewritten history does not", async () => {
  for (let n = 1; n <= 12; n++) for (let m = 1; m <= n; m++) {
    assert.equal(await verifyConsistency(m, n, fromHex(M.trees[String(m)].root), fromHex(M.trees[String(n)].root), b(M.trees[String(n)].consistency[String(m)])), true, `${m}->${n}`);
  }
  // the root of 8 is not a prefix of a different tree of 12
  assert.equal(await verifyConsistency(8, 12, fromHex(M.trees["8"].root), fromHex(M.trees["11"].root), b(M.trees["12"].consistency["8"])), false);
});
test("a signed checkpoint verifies, and tampering with its text or signature does not", async () => {
  const cp = M.checkpoint;
  const ok = await verifyCheckpoint(cp, cp.keys);
  assert.deepEqual([ok.valid, ok.size, ok.root], [true, 12, cp.root]);
  assert.equal((await verifyCheckpoint({ ...cp, text: cp.text.replace("size=12", "size=13") }, cp.keys)).valid, false);
  assert.equal((await verifyCheckpoint({ ...cp, signature: cp.signature.slice(0, -2) + "AA" }, cp.keys)).valid, false);
  assert.equal((await verifyCheckpoint(cp, {})).valid, false);
});
