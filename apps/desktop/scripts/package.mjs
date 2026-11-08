// Builds a standalone Windows app:  node scripts/package.mjs   ->  dist/Pramaan-win32-x64/Pramaan.exe
// No runtime dependencies are bundled (the shell uses only Electron's own modules), so the package is
// just Electron + src/ + assets/.
import { packager } from "@electron/packager";
import { writeFileSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const [out] = await packager({
  dir: root,
  out: path.join(root, "dist"),
  name: "Pramaan",
  executableName: "Pramaan",
  platform: process.platform === "darwin" ? "darwin" : process.platform === "linux" ? "linux" : "win32",
  arch: "x64",
  icon: path.join(root, "assets", "icon.ico"),
  appCopyright: "Pramaan",
  overwrite: true,
  asar: true,
  prune: false,
  ignore: [/^\/node_modules($|\/)/, /^\/scripts($|\/)/, /^\/dist($|\/)/, /^\/pnpm-lock\.yaml$/, /\.md$/],
  win32metadata: { CompanyName: "Pramaan", FileDescription: "Pramaan — Who's Who India, verified", ProductName: "Pramaan" },
});
// Point the packaged app at your server without rebuilding: edit config.json next to Pramaan.exe.
writeFileSync(path.join(out, "config.json"), JSON.stringify({ url: "http://localhost:3100" }, null, 2) + "\n");
console.log("Packaged:", out);
