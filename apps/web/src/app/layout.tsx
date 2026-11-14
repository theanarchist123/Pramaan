import type { Metadata, Viewport } from "next";
// Fonts are self-hosted from npm (no network at build time, unlike next/font/google).
import "@fontsource-variable/bricolage-grotesque/wght.css";
import "@fontsource-variable/inter/wght.css";
import "@fontsource-variable/noto-sans-devanagari/wght.css";
import "./globals.css";
import { Providers } from "@/components/providers";
import { FloatingNav } from "@/components/nav/floating-nav";
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
  viewportFit: "cover", // lets the page use the whole screen in the Android/iOS app; the nav and footer already pad for the safe areas
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FFB81C" },
    { media: "(prefers-color-scheme: dark)", color: "#0F1020" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-dvh">
        <Providers>
          <SkipLink />
          <FloatingNav />
          <ConnectionBanner />
          <PwaRegister />
          <main id="main" className="pt-28 pb-[env(safe-area-inset-bottom)] md:pt-16">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
