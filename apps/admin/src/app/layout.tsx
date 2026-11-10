import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Pramaan staff console", robots: { index: false, follow: false } };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" data-density="compact">
      <body>{children}</body>
    </html>
  );
}
