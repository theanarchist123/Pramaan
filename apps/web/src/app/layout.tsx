import type { Metadata, Viewport } from "next";
import { Fraunces, Inter, Noto_Sans_Devanagari } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/site-header";
import { SkipLink } from "@/components/skip-link";
import { ConnectionBanner } from "@/components/connection-banner";
import { PwaRegister } from "@/components/pwa-register";

const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces", display: "swap" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const deva = Noto_Sans_Devanagari({
  subsets: ["devanagari"],
  weight: ["400", "500", "600"],
  variable: "--font-deva",
  display: "swap",
});

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
    <html lang="en" suppressHydrationWarning className={`${fraunces.variable} ${inter.variable} ${deva.variable}`}>
      <body className="min-h-dvh">
        <Providers>
          <SkipLink />
          <SiteHeader />
          <ConnectionBanner />
          <PwaRegister />
          <main id="main">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
