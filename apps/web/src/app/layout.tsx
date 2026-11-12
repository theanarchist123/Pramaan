import type { Metadata, Viewport } from "next";
// Fonts are self-hosted from npm (no network at build time, unlike next/font/google).
import "@fontsource-variable/fraunces/wght.css";
import "@fontsource-variable/inter/wght.css";
import "@fontsource-variable/noto-sans-devanagari/wght.css";
import "./globals.css";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/site-header";
import { SkipLink } from "@/components/skip-link";
import { ConnectionBanner } from "@/components/connection-banner";
import { PwaRegister } from "@/components/pwa-register";

export const metadata: Metadata = {
  title: { default: "Pramaan — Who's Who India, verified", template: "%s · Pramaan" },
  description:
    "A registry of notable Indians where every claim carries evidence and every certificate is cryptographically verifiable. Don't claim it. Prove it.",
  applicationName: "Pramaan",
  icons: { icon: "/icons/icon-192.png", apple: "/icons/apple-touch-icon.png" },
  appleWebApp: { capable: true, title: "Pramaan", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8f4ec" },
    { media: "(prefers-color-scheme: dark)", color: "#1c1814" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-dvh">
        <Providers>
          <SkipLink />
          <SiteHeader />
          <ConnectionBanner />
          <PwaRegister />
          <main id="main" className="pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
