// WCAG 2.x contrast gate for the design tokens (spec UI-01). Reads tokens.css, computes every ratio, fails the build if any
// text pair is below its target. Run: `node scripts/contrast.mjs`  (or `pnpm --filter @pramaan/ui test`).
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../tokens.css", import.meta.url), "utf8");

/** Parse the custom properties of one selector block (":root" or ".dark") into { name: "#rrggbb" | "rgb(...)" }. */
function block(selector) {
  const start = css.indexOf(`\n${selector} {`);
  if (start < 0) throw new Error(`no ${selector} block in tokens.css`);
  const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("\n}", start));
  const out = {};
  for (const m of body.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}

const light = block(":root");
const dark = { ...light, ...block(".dark") }; // .dark overrides; unchanged tokens (e.g. --paper) fall through

const hex = (v) => {
  const m = /^#([0-9a-f]{6})$/i.exec(v ?? "");
  return m ? [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)) : null;
};
const lin = (c) => ((c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

// [foreground token, background token, minimum ratio, why]
const TEXT = 4.5;
const pairs = [
  ["ink", "bond", TEXT, "body text on the page"],
  ["ink", "surface", TEXT, "body text on cards"],
  ["ink-muted", "bond", TEXT, "secondary text on the page"],
  ["ink-muted", "surface", TEXT, "secondary text on cards"],
  ["stamp", "bond", TEXT, "links and actions on the page"],
  ["stamp", "surface", TEXT, "links and actions on cards"],
  ["stamp", "stamp-tint", TEXT, "selected state text"],
  ["verified", "surface", TEXT, "verified text on cards"],
  ["verified", "verified-tint", TEXT, "verified chip"],
  ["seal", "surface", TEXT, "alert / revoked text on cards"],
  ["seal", "seal-tint", TEXT, "alert chip"],
  ["caution", "surface", TEXT, "caution text on cards"],
  ["caution", "caution-tint", TEXT, "caution chip"],
  ["paper-ink", "paper", TEXT, "text on a paper object (certificate, evidence slip)"],
  ["paper-ink-muted", "paper", TEXT, "secondary text on a paper object"],
];
// Sector colours are marks (spines, dots, rings): the spec requires every sector to ALSO carry an icon and a label, so
// 3:1 (WCAG non-text contrast) is the gate; the spec's stronger claim (4.2 light / 7.6 dark) is reported, not gated.
const sectors = Object.keys(light).filter((k) => k.startsWith("sector-"));

let failed = 0;
const report = (theme, tokens) => {
  console.log(`\n${theme}`);
  const bg = (n) => hex(tokens[n]);
  for (const [fg, back, min, why] of pairs) {
    const a = hex(tokens[fg]), b = bg(back);
    if (!a || !b) { console.log(`  ?  ${fg} on ${back}: not a plain hex colour`); failed++; continue; }
    const r = ratio(a, b);
    const ok = r >= min;
    if (!ok) failed++;
    console.log(`  ${ok ? "ok" : "FAIL"}  ${fg.padEnd(10)} on ${back.padEnd(13)} ${r.toFixed(2).padStart(5)}:1  (needs ${min})  ${why}`);
  }
  let weak = 0;
  for (const s of sectors) {
    const r = ratio(hex(tokens[s]), bg("surface"));
    if (r < 3) { failed++; console.log(`  FAIL  ${s} on surface ${r.toFixed(2)}:1 (needs 3 as a non-text mark)`); }
    else if (r < (theme === "light" ? 4.2 : 7.6)) { weak++; console.log(`  note  ${s} on surface ${r.toFixed(2)}:1 is below the spec's ${theme === "light" ? "4.2" : "7.6"}:1 claim (still passes the 3:1 mark gate; it always carries an icon and label)`); }
  }
  console.log(`  sector marks: ${sectors.length} checked against 3:1; ${weak} are below the spec's stronger target (${theme === "light" ? "4.2" : "7.6"}:1)`);
};

report("light", light);
report("dark", dark);
console.log(failed ? `\n${failed} contrast check(s) failed.` : "\nAll contrast checks passed.");
process.exit(failed ? 1 : 0);
