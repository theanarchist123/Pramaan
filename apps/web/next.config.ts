import path from "node:path";
import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";
const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Verification pages must not be framable (clickjacking); everything else is locked to our own origin + the API.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  // ${api}: certificate QR codes. images.unsplash.com: HOTLINKED sector photographs from the approved set (Unsplash API
  // terms forbid re-hosting). Certificates never use it: they use self-hosted photos, and the render blocks third parties.
  `img-src 'self' data: blob: ${api} https://images.unsplash.com`,
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
  transpilePackages: ["@pramaan/ui", "@pramaan/verify"], // workspace package shipped as TypeScript source
  // The web app lives in a pnpm workspace: trace dependencies from the repo root so the standalone bundle is complete.
  outputFileTracingRoot: path.join(__dirname, "../../"),
  // Lets a production build live beside a running `next dev` without clobbering its .next folder.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Staff work lives in the separate admin console (its own sign-in and cookie). The old /admin pages in this app signed in as a member, which the API now refuses (401),
  // so they send people to the console instead. Set NEXT_PUBLIC_ADMIN_URL to the console's address.
  async redirects() {
    const admin = (process.env.NEXT_PUBLIC_ADMIN_URL || "http://localhost:3001").replace(/\/$/, "");
    return [
      { source: "/admin", destination: `${admin}/`, permanent: false },
      { source: "/admin/builder", destination: `${admin}/builder`, permanent: false },
      { source: "/admin/:path*", destination: `${admin}/`, permanent: false },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
