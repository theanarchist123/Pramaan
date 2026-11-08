// Live check of the TS SDK against a running API. Usage: node test-live.mjs <apiUrl> <sig.json>
import { Pramaan, PramaanError, verifyWebhook } from "./dist/index.js";
import { readFileSync } from "node:fs";
const [, , api, sigFile] = process.argv;
const { secret, header, body } = JSON.parse(readFileSync(sigFile, "utf-8"));
const p = new Pramaan({ baseUrl: api });
let n = 0;
const ok = (c, m) => { if (!c) { console.log("FAIL:", m); process.exitCode = 1; } else { n++; console.log("ok  :", m); } };

const log = await (await fetch(`${api}/v1/transparency?limit=1`)).json();
const code = log[0].certificate_code;
const v = await p.verify(code.toLowerCase());
ok(v.valid === true && v.signature_ok, `verify ${code}`);
const forged = await p.checkPayload(code, { ...v.payload, full_name: "Someone Else" });
ok(forged.valid === false && forged.changed_fields.includes("full_name"), "forgery detected, names full_name");
const s = await p.search("clean energy researcher Karnataka", { limit: 3 });
ok(s.results.length > 0 && s.results[0].reasons.length >= 0, `search → ${s.results[0]?.full_name}`);
ok((await p.transparencyOk()).ok, "transparency chain intact");
ok((await p.publicKeys()).keys[0].crv === "Ed25519", "public key published");
ok(p.badgeUrl("prm-x").endsWith("/v1/badge/certificate/PRM-X.svg"), "badge url");
try { await p.myProfiles(); ok(false, "should need a key"); } catch (e) { ok(e instanceof PramaanError && e.status === 401, "401 without a key → PramaanError"); }
// cross-language: the PYTHON server signed this, the TS SDK verifies it
ok(await verifyWebhook(secret, header, body), "TS verifies a Python-signed webhook");
ok(!(await verifyWebhook(secret, header, body + " ")), "TS rejects a tampered body");
ok(!(await verifyWebhook("whsec_wrong", header, body)), "TS rejects the wrong secret");
console.log(`${n} checks passed`);
