import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle: what the Docker image runs.
  output: "standalone",
  // Lets a production build live beside a running `next dev` without clobbering its .next folder.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
