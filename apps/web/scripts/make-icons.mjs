// Renders the Pramaan seal to PNG app icons (any + maskable + apple-touch). Run: node scripts/make-icons.mjs
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";

const petals = Array.from({ length: 8 }, (_, i) => i * 45);
const seal = (bg, scale) => `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="100%" height="100%">
  <rect width="40" height="40" fill="${bg}"/>
  <g transform="translate(20 20) scale(${scale})">
    ${petals.map((d) => `<ellipse rx="4.2" ry="9" transform="rotate(${d}) translate(0 -9)" fill="#e8821a" fill-opacity="0.85"/>`).join("")}
    <circle r="8.5" fill="#fbf6ec"/><circle r="8.5" fill="none" stroke="#2b2d6e" stroke-width="1.4"/>
    <path d="M-3.8 0.3 L-1 3.2 L4.2 -2.8" fill="none" stroke="#2b2d6e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
</svg>`;

const jobs = [
  ["icon-192.png", 192, "#f8f4ec", 1.45],
  ["icon-512.png", 512, "#f8f4ec", 1.45],
  ["icon-maskable-512.png", 512, "#f8f4ec", 1.05], // keep the seal inside the maskable safe zone
  ["apple-touch-icon.png", 180, "#f8f4ec", 1.35],
];
const b = await chromium.launch();
for (const [file, size, bg, scale] of jobs) {
  const p = await b.newPage({ viewport: { width: size, height: size } });
  await p.setContent(`<body style="margin:0">${seal(bg, scale)}</body>`);
  writeFileSync(`public/icons/${file}`, await p.screenshot({ type: "png" }));
  console.log("wrote", file);
}
await b.close();
