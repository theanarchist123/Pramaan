import type { Metadata } from "next";
import "./globals.css";
import { DeskNav } from "@/components/desk-nav";

export const metadata: Metadata = { title: "Pramaan staff console", robots: { index: false, follow: false } };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" data-density="compact">
      <body>
        <DeskNav />
        {children}
      </body>
    </html>
  );
}
