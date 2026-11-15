import path from "node:path";
import type { NextConfig } from "next";

// Where the browser sends API calls. Locally that is the API itself (http://localhost:8000). On a free host (the console on *.vercel.app, the API on *.onrender.com)
// the staff cookie is SameSite=Strict, which a browser withholds on calls to another site, so there it is a path on the console's OWN address
// (NEXT_PUBLIC_API_URL=/staff/api) that the route handler in src/app/api/[...path]/route.ts forwards to the API (API_INTERNAL_URL). The browser then only ever talks to one site.
const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const isDev = process.env.NODE_ENV !== "production";

// The staff console loads nothing from third parties and cannot be framed. Its API calls go to the API origin only.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  `connect-src 'self'${api.startsWith("http") ? ` ${api}` : ""}${isDev ? " ws://localhost:*" : ""}`,
  "frame-ancestors 'none'", "base-uri 'self'", "form-action 'self'", "object-src 'none'",
].join("; ");

// Served under /staff so the console shares the site's address (the web app proxies /staff to this server). Its own cookie, sign-in and CSP are unchanged.
const nextConfig: NextConfig = {
  basePath: "/staff",
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "../../"),
  transpilePackages: ["@pramaan/ui"],
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // The console lives under /staff (that is what lets it share the member site's address locally), but nobody should have to type it:
  // the bare address of the staff site goes straight to the sign-in screen.
  async redirects() {
    return [
      { source: "/", destination: "/staff", permanent: false, basePath: false },
      { source: "/login", destination: "/staff/login", permanent: false, basePath: false },
    ];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "Content-Security-Policy", value: csp },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
        { key: "Cache-Control", value: "no-store" }, // staff screens are never cached
      ],
    }];
  },
};

export default nextConfig;
