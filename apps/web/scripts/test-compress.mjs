// Pure-function checks for the upload shrinker. Run: node scripts/test-compress.mjs
import assert from "node:assert/strict";
import { shouldCompress, targetSize, COMPRESS_OVER_BYTES } from "../src/lib/compress-image.ts";

assert.equal(shouldCompress({ type: "image/jpeg", size: COMPRESS_OVER_BYTES + 1 }), true);
assert.equal(shouldCompress({ type: "image/jpeg", size: 1000 }), false, "small files are never re-encoded (keeps their metadata)");
assert.equal(shouldCompress({ type: "application/pdf", size: COMPRESS_OVER_BYTES * 3 }), false, "PDFs are untouched");
assert.equal(shouldCompress({ type: "image/gif", size: COMPRESS_OVER_BYTES * 3 }), false);
assert.deepEqual(targetSize(4000, 3000), { w: 2400, h: 1800 });
assert.deepEqual(targetSize(1000, 800), { w: 1000, h: 800 }, "never enlarges");
console.log("compress-image: 6 checks passed");
