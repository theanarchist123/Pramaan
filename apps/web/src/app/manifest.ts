import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Pramaan — Who's Who India, verified",
    short_name: "Pramaan",
    description: "A registry of notable Indians where every claim carries evidence and every certificate is verifiable by anyone.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#f8f4ec",
    theme_color: "#e8821a",
    categories: ["productivity", "reference"],
    lang: "en",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Verify a certificate", short_name: "Verify", url: "/verify", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Create my verified profile", short_name: "My profile", url: "/onboard", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Search the registry", short_name: "Search", url: "/directory", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
    ],
  };
}
