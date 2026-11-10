"use client";

import { ThemeProvider } from "next-themes";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import { MotionPreferenceProvider } from "@/lib/motion-preference";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <I18nProvider>
        <AuthProvider>
          <MotionPreferenceProvider>
            {children}
            <Toaster position="top-center" richColors />
          </MotionPreferenceProvider>
        </AuthProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
