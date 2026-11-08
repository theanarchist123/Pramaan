"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { Command as CommandIcon, Languages, LogOut, Menu, Moon, Sun, Type } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { CommandPalette } from "@/components/command-palette";
import { useAuth } from "@/lib/auth";
import { useI18n, type Key } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const LARGE_KEY = "pramaan.largeText";

export function toggleLargeText() {
  const el = document.documentElement;
  const next = el.dataset.largeText !== "true";
  el.dataset.largeText = String(next);
  try {
    localStorage.setItem(LARGE_KEY, String(next));
  } catch {
    /* per-viewer convenience only */
  }
}

const NAV: { href: string; key: Key }[] = [
  { href: "/directory", key: "nav.directory" },
  { href: "/verify", key: "nav.verify" },
  { href: "/mission-control", key: "nav.mission" },
  { href: "/developers", key: "nav.developers" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const { user, logout } = useAuth();
  const { lang, setLang, t } = useI18n();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      if (localStorage.getItem(LARGE_KEY) === "true") document.documentElement.dataset.largeText = "true";
    } catch {
      /* ignore */
    }
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
        <Link href="/" aria-label="Pramaan home">
          <Logo />
        </Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {[...NAV, ...(user?.role === "admin" ? [{ href: "/admin", key: "nav.admin" as Key }] : [])].map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                pathname.startsWith(n.href) && "bg-muted text-foreground",
              )}
            >
              {t(n.key)}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            className="hidden gap-2 text-muted-foreground sm:inline-flex"
            onClick={() => setPaletteOpen(true)}
          >
            <CommandIcon className="size-3.5" /> <span>{t("nav.search")}</span>
            <kbd className="rounded bg-muted px-1.5 text-[10px]">Ctrl K</kbd>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label={t("nav.menu")}
            onClick={() => setPaletteOpen(true)}
          >
            <Menu />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="gap-1 px-2 font-medium"
            aria-label={`${lang === "en" ? "हिन्दी" : "EN"} — ${t("nav.language")}`}
            lang={lang === "en" ? "hi" : "en"}
            onClick={() => setLang(lang === "en" ? "hi" : "en")}
          >
            <Languages className="size-4" /> {lang === "en" ? "हिन्दी" : "EN"}
          </Button>
          <Button variant="ghost" size="icon" aria-label={t("nav.largeText")} onClick={toggleLargeText}>
            <Type />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("nav.darkMode")}
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          >
            {mounted && resolvedTheme === "dark" ? <Sun /> : <Moon />}
          </Button>
          {user ? (
            <>
              <Link href="/me" className="hidden px-2 text-sm text-muted-foreground hover:text-foreground sm:block">
                {user.name || user.email}
              </Link>
              <Button variant="ghost" size="icon" aria-label={t("nav.signout")} onClick={logout}>
                <LogOut />
              </Button>
            </>
          ) : (
            <Button size="sm" render={<Link href="/auth" />} nativeButton={false}>
              {t("nav.signin")}
            </Button>
          )}
        </div>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </header>
  );
}
