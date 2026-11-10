"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

// Chrome/Edge/Samsung Internet fire this when the app is installable; the event is not in TypeScript's DOM types.
interface InstallEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

/**
 * "Install app" button. Browsers rarely show their own install prompt (and iPhone Safari never does), so this
 * triggers the real install dialog where the browser allows it, and explains the manual steps where it doesn't.
 * Hidden once the app is already installed / running standalone.
 */
export function InstallButton() {
  const { t } = useI18n();
  const [event, setEvent] = useState<InstallEvent | null>(null);
  const [installed, setInstalled] = useState(true); // hidden until we know (avoids a flash and SSR mismatch)

  useEffect(() => {
    const standalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      (navigator as unknown as { standalone?: boolean }).standalone === true;
    setInstalled(standalone);
    const onPrompt = (e: Event) => {
      e.preventDefault(); // keep it for our button
      setEvent(e as InstallEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setEvent(null);
      toast.success("Pramaan is installed");
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (installed) return null;

  async function install() {
    if (event) {
      await event.prompt();
      const choice = await event.userChoice;
      if (choice.outcome === "accepted") setEvent(null);
      return;
    }
    const ua = navigator.userAgent;
    const ios = /iPhone|iPad|iPod/i.test(ua);
    toast.info(
      ios
        ? "On iPhone/iPad: tap the Share button in Safari, then “Add to Home Screen”."
        : "Open your browser menu (⋮) and choose “Install app” or “Add to Home screen”. (Use Chrome or Edge if you don't see it.)",
      { duration: 10000, position: "bottom-center" }, // not top: it would cover this button
    );
  }

  return (
    <Button variant="ghost" size="sm" className="gap-1 px-2 font-medium" onClick={install}>
      <Download className="size-4" /> <span className="hidden sm:inline">{t("nav.install")}</span>
      <span className="sr-only sm:hidden">{t("nav.install")}</span>
    </Button>
  );
}
