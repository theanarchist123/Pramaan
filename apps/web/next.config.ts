import path from "node:path";
import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";
const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Verification pages must not be framable (clickjacking); everything else is locked to our own origin + the API.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${api}`, // ${api}: certificate QR codes are served by the API
  "font-src 'self' data:",
  `connect-src 'self' ${api}${isDev ? " ws: http://localhost:* http://127.0.0.1:*" : ""}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), geolocation=(), microphone=(self)" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
];

const nextConfig: NextConfig = {
  // Self-contained server bundle: what the Docker image runs.
  output: "standalone",
  // The web app lives in a pnpm workspace: trace dependencies from the repo root so the standalone bundle is complete.
  outputFileTracingRoot: path.join(__dirname, "../../"),
  // Lets a production build live beside a running `next dev` without clobbering its .next folder.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
