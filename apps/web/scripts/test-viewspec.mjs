// The interpreter safety helpers, checked with node. Run: node scripts/test-viewspec.mjs
import assert from "node:assert/strict";
import { resolvePath, safeBlocks, bindIsAllowed, asEntries } from "../src/lib/viewspec.ts";

assert.equal(resolvePath({ a: { b: 3 } }, "a.b"), 3);
assert.equal(resolvePath({ a: 1 }, "__proto__.x"), undefined, "prototype keys never resolve");
assert.equal(resolvePath({ a: 1 }, "constructor"), undefined);
assert.equal(resolvePath({}, "toString"), undefined, "inherited properties never resolve");
assert.equal(resolvePath({ a: 1 }, "A b"), undefined);
assert.deepEqual(resolvePath({ a: 1 }, ""), { a: 1 });
assert.equal(bindIsAllowed({ endpoint: "/v1/stats/map", path: "total" }), true);
assert.equal(bindIsAllowed({ endpoint: "/v1/admin/overview" }), false);
assert.equal(bindIsAllowed({ endpoint: "https://evil.example/x" }), false);
const blocks = safeBlocks({ blocks: [
  { type: "heading", text: "Ok", level: 2 },
  { type: "script", src: "x" },
  { type: "text", text: "<img src=x onerror=alert(1)>" },
  { type: "text", text: "go to https://evil.example" },
  { type: "stat", label: "n", bind: { endpoint: "/v1/admin/overview", path: "x" } },
  { type: "stat", label: "n", bind: { endpoint: "/v1/stats/map", path: "total" } },
] });
assert.deepEqual(blocks.map((b) => b.type), ["heading", "stat"]);
assert.deepEqual(safeBlocks(null), []);
assert.deepEqual(asEntries({ a: 1, b: { c: 2 }, d: "x" }), [["a", 1], ["d", "x"]]);
console.log("viewspec interpreter: 14 checks passed");
