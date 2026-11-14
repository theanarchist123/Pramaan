import type { Metadata } from "next";
import "./globals.css";
import { DeskNav } from "@/components/desk-nav";

export const metadata: Metadata = { title: "Pramaan staff console", robots: { index: false, follow: false } };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" data-density="compact" suppressHydrationWarning>
      <head>
        {/* Dark is the default; a saved choice of light is applied before the first paint so there is no flash. */}
        <script dangerouslySetInnerHTML={{ __html: "try{if(localStorage.getItem('desk-theme')==='light')document.documentElement.classList.remove('dark')}catch(e){}" }} />
      </head>
      <body>
        <DeskNav />
        {children}
      </body>
    </html>
  );
}
