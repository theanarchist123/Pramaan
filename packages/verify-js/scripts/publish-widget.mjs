// Copies the verifier and the <pramaan-verify> element into the web app's public folder, so they are served from the same origin as the site
// (and the site's Content-Security-Policy needs no new script source). Run by the web app's predev / prebuild.
import { copyFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const from = (f) => fileURLToPath(new URL(`../src/${f}`, import.meta.url));
const dir = fileURLToPath(new URL("../../../apps/web/public/pramaan-verify/", import.meta.url));
mkdirSync(dir, { recursive: true });
for (const f of ["index.js", "element.js"]) copyFileSync(from(f), dir + f);
console.log("published the verify widget to apps/web/public/pramaan-verify/");
