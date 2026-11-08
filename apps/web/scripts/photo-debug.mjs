import { chromium } from "playwright";
const code = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1200, height: 900 } });
const fails = [];
p.on("requestfailed", (r) => fails.push(`${r.url().slice(0, 90)} :: ${r.failure()?.errorText}`));
p.on("console", (m) => m.type() === "error" && fails.push("console: " + m.text().slice(0, 140)));
await p.goto(`http://localhost:3100/verify/${code}`);
await p.waitForTimeout(3500);
const info = await p.evaluate(() =>
  [...document.querySelectorAll("#certificate img")].map((i) => ({
    src: i.src.slice(0, 70), complete: i.complete, w: i.naturalWidth, cors: i.crossOrigin,
  })),
);
console.log(JSON.stringify(info, null, 1));
console.log("failures:", fails);
await b.close();
