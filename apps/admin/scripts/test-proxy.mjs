// The free-hosting proxy forwards ONLY what the console needs, and says so plainly when it is not connected.
// Run: node scripts/test-proxy.mjs  (TypeScript is transpiled with the project's own compiler, as Next does)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const dir = path.dirname(fileURLToPath(import.meta.url)).replace(/scripts$/, "");
const compile = (rel) => ts.transpileModule(readFileSync(path.join(dir, rel), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
const run = (js, extra = {}) => { const mod = { exports: {} }; new Function("require", "module", "exports", "__dirname", ...Object.keys(extra), js)(require, mod, mod.exports, dir, ...Object.values(extra)); return mod.exports; };

// 1. the allow-list
const { isAllowed, apiTarget } = run(compile("src/lib/proxy-allow.ts"));
for (const ok of ["v1/admin/auth/login", "v1/admin/review/abc/decide", "v1/auth/mfa/status", "v1/search", "v1/images/sector/Science"]) assert.ok(isAllowed(ok), `allows ${ok}`);
for (const bad of ["v1/auth/login", "v1/auth/me", "v1/profiles", "v1/admin", "v1/search/x", "", "v1/admin/../auth/login", "v1/admin//x", "v1/admin/%2e%2e/x", "v1\admin/x", "healthz", "v1/auth/mfa"]) assert.ok(!isAllowed(bad), `refuses ${JSON.stringify(bad)}`);

// 2. the target is read from the environment given, tidied, and empty when unset
assert.equal(apiTarget({ API_INTERNAL_URL: "https://api.example.test/" }), "https://api.example.test");
assert.equal(apiTarget({ API_INTERNAL_URL: " https://api.example.test// " }), "https://api.example.test");
assert.equal(apiTarget({}), "");

// 3. the route handler: missing setting -> a clear 503; a refused path -> 404; the allowed path is forwarded with its cookie and Origin, and Set-Cookie comes back
const routeJs = compile("src/app/api/[...path]/route.ts").replace(/require\("@\/lib\/proxy-allow"\)/, "__allow");
const calls = [];
const fakeFetch = async (url, init) => { calls.push({ url, init }); const h = new Headers({ "content-type": "application/json" }); h.append("set-cookie", "__Host-pramaan_admin=abc; Path=/; Secure; HttpOnly; SameSite=Strict"); return new Response('{"ok":true}', { status: 200, headers: h }); };
const loadRoute = (env) => run(routeJs, { __allow: { isAllowed, apiTarget: () => apiTarget({ API_INTERNAL_URL: env }) }, fetch: fakeFetch });
const req = (m, p, headers = {}, body) => new Request(`https://staff.example.test/staff/api/${p}`, { method: m, headers, body });
const ctx = (p) => ({ params: Promise.resolve({ path: p.split("/") }) });

let r = await loadRoute("").POST(req("POST", "v1/admin/auth/login", {}, "{}"), ctx("v1/admin/auth/login"));
assert.equal(r.status, 503); assert.match((await r.json()).detail, /API_INTERNAL_URL is not set/);

const route = loadRoute("https://api.example.test/");
r = await route.GET(req("GET", "v1/auth/login"), ctx("v1/auth/login"));
assert.equal(r.status, 404); assert.equal(calls.length, 0, "a refused path never leaves the console");

r = await route.POST(req("POST", "v1/admin/auth/login?x=1", { "content-type": "application/json", cookie: "a=b", origin: "https://staff.example.test", authorization: "Bearer SECRET" }, '{"email":"a@b.co"}'), ctx("v1/admin/auth/login"));
assert.equal(r.status, 200);
assert.equal(calls[0].url, "https://api.example.test/v1/admin/auth/login?x=1");
assert.equal(calls[0].init.headers.get("origin"), "https://staff.example.test");
assert.equal(calls[0].init.headers.get("cookie"), "a=b");
assert.equal(calls[0].init.headers.get("authorization"), null, "no Authorization header is passed on");
assert.match(r.headers.getSetCookie()[0], /^__Host-pramaan_admin=abc/);
console.log("staff proxy: all checks passed");
