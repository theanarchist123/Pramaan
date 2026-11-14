// The free-hosting proxy (rewrites in next.config.ts) forwards ONLY what the console needs, and only to the configured API.
// Run: node scripts/test-proxy.mjs  (the config is transpiled with the project's own TypeScript, as Next does, then evaluated)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const dir = path.dirname(fileURLToPath(import.meta.url)).replace(/scripts$/, "");
const src = readFileSync(path.join(dir, "next.config.ts"), "utf8");
const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;

async function load(env) {
  const saved = { ...process.env };
  Object.assign(process.env, env);
  try {
    const mod = { exports: {} };
    new Function("require", "module", "exports", "__dirname", js)(require, mod, mod.exports, dir);
    const cfg = mod.exports.default;
    const csp = (await cfg.headers())[0].headers.find((h) => h.key === "Content-Security-Policy").value;
    return { basePath: cfg.basePath, r: await cfg.rewrites(), csp };
  } finally {
    process.env = saved;
  }
}

const none = await load({ API_INTERNAL_URL: "", NEXT_PUBLIC_API_URL: "" });
assert.deepEqual(none.r, [], "with no API_INTERNAL_URL nothing is forwarded");

const on = await load({ API_INTERNAL_URL: "https://api.example.test/", NEXT_PUBLIC_API_URL: "/staff/api" });
assert.equal(on.basePath, "/staff");
for (const rule of on.r) {
  assert.ok(rule.source.startsWith("/api/v1/"), "every forwarded path is under /api/v1/");
  assert.ok(rule.destination.startsWith("https://api.example.test/v1/"), "and goes only to the configured API");
  assert.ok(!rule.destination.replace("https://", "").includes("//"), "no doubled slashes");
}
const forwarded = on.r.map((x) => x.source).join(" ");
for (const must of ["/api/v1/admin/", "/api/v1/auth/mfa/", "/api/v1/search"]) assert.ok(forwarded.includes(must), `forwards ${must}`);
for (const never of ["/api/v1/auth/login", "/api/v1/profiles", "/api/:path*", "/v1/auth/me"]) assert.ok(!forwarded.includes(never), `does not forward ${never}`);
assert.ok(!on.csp.includes("/staff/api"), "a relative API path is not put into the CSP as a source");
assert.match(on.csp, /connect-src 'self'[; ]/);

const local = await load({ API_INTERNAL_URL: "", NEXT_PUBLIC_API_URL: "http://localhost:8000" });
assert.ok(local.csp.includes("connect-src 'self' http://localhost:8000"), "locally the CSP allows the API origin as before");
console.log("staff proxy config: all checks passed");
