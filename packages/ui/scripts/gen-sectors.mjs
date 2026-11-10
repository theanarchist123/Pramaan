// Regenerates src/sectors.ts from tokens.css (the single source of the sector colours). Run: node scripts/gen-sectors.mjs
import { readFileSync, writeFileSync } from "node:fs";

const css = readFileSync(new URL("../tokens.css", import.meta.url), "utf8");
const [lightCss, darkCss] = css.split(".dark {");
const grab = (s) => Object.fromEntries([...s.matchAll(/--sector-([a-z-]+):\s*(#[0-9A-Fa-f]{6})/g)].map((m) => [m[1], m[2]]));
const light = grab(lightCss), dark = grab(darkCss);
const META = [["Energy","energy","zap"],["Agriculture","agriculture","sprout"],["Healthcare","healthcare","heart-pulse"],["Technology","technology","cpu"],["Science","science","flask-conical"],["Media","media","newspaper"],["Business","business","briefcase"],["Education","education","graduation-cap"],["Literature","literature","book-open"],["Social Work","social-work","hand-heart"],["Arts & Culture","arts-culture","palette"],["Sports","sports","trophy"],["Law","law","scale"],["Public Service","public-service","landmark"]];
const rows = META.map(([name, slug, icon]) => `  { name: "${name}", slug: "${slug}", icon: "${icon}", light: "${light[slug]}", dark: "${dark[slug]}" },`);
writeFileSync(new URL("../src/sectors.ts", import.meta.url), [
  "// GENERATED from tokens.css by scripts/gen-sectors.mjs: do not edit by hand.",
  "export interface Sector { name: string; slug: string; icon: string; light: string; dark: string }",
  "export const SECTORS: readonly Sector[] = [", ...rows, "] as const;", "",
  "export const sectorByName = (name: string): Sector | undefined => SECTORS.find((s) => s.name === name);", "",
].join("\n"));
console.log(`wrote ${META.length} sectors`);
