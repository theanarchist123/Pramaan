"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { Command as CommandIcon, Download, Languages, LogOut, Menu as MenuIcon, Search, ScanLine, ShieldCheck, UserRound, UserRoundPlus, Library } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { CommandPalette } from "@/components/command-palette";
import { useInstall } from "@/components/install-button";
import {
  DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth";
import { useMotionPreference } from "@/lib/motion-preference";
import { useI18n, type Key } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const LARGE_KEY = "pramaan.largeText";

export function toggleLargeText(): boolean {
  const el = document.documentElement;
  const next = el.dataset.largeText !== "true";
  el.dataset.largeText = String(next);
  try {
    localStorage.setItem(LARGE_KEY, String(next));
  } catch {
    /* per-viewer convenience only */
  }
  return next;
}

// The public nav (spec 6.0): four places. Mission Control and the staff console are not here; staff reach theirs from the account menu.
const NAV: { href: string; key: Key }[] = [
  { href: "/directory", key: "nav.directory" },
  { href: "/verify", key: "nav.verify" },
  { href: "/transparency", key: "nav.transparency" },
  { href: "/developers", key: "nav.developers" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const { user, logout } = useAuth();
  const { lang, setLang, t } = useI18n();
  const { reduced, setReduced } = useMotionPreference();
  const { available: canInstall, install } = useInstall();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [large, setLarge] = useState(false);
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      if (localStorage.getItem(LARGE_KEY) === "true") {
        document.documentElement.dataset.largeText = "true";
        setLarge(true);
      }
    } catch {
      /* ignore */
    }
    // The header compresses once the page has scrolled (spec M-17). The height changes at once: no animation on layout properties.
    const onScroll = () => setCompact(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const initials = (user?.name || user?.email || "?").trim().slice(0, 1).toUpperCase();
  const recordHref = user ? "/me" : "/onboard";
  const active = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-md">
        <div className={cn("mx-auto flex max-w-7xl items-center gap-4 px-4", compact ? "h-12" : "h-16")}>
          <Link href="/" aria-label="Pramaan home">
            <Logo />
          </Link>
          <nav className="hidden items-center gap-1 lg:flex" aria-label={t("nav.primary")}>
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active(n.href) ? "page" : undefined}
                className={cn("px-3 py-4 text-sm text-muted-foreground transition-colors hover:text-foreground", active(n.href) && "font-medium text-foreground shadow-[inset_0_-2px_0_var(--stamp)]")}
              >
                {t(n.key)}
              </Link>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1">
            <Button variant="outline" size="sm" aria-label={t("nav.search")} className="gap-2 text-muted-foreground" onClick={() => setPaletteOpen(true)}>
              <Search aria-hidden className="size-4 sm:hidden" /><CommandIcon aria-hidden className="hidden size-3.5 sm:block" /> <span className="hidden lg:inline">{t("nav.search")}</span>
              <kbd className="hidden rounded bg-muted px-1.5 text-[10px] lg:inline">Ctrl K</kbd>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="gap-1 px-2 font-medium"
              aria-label={`${lang === "en" ? "हिन्दी" : "EN"} — ${t("nav.language")}`}
              lang={lang === "en" ? "hi" : "en"}
              onClick={() => setLang(lang === "en" ? "hi" : "en")}
            >
              <Languages className="size-4" /> <span className="hidden sm:inline">{lang === "en" ? "हिन्दी" : "EN"}</span>
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button variant="ghost" size="icon" aria-label={t("nav.account")}>
                    {user ? (
                      <span aria-hidden className="inline-flex size-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">{initials}</span>
                    ) : (
                      <MenuIcon />
                    )}
                  </Button>
                }
              />
              <DropdownMenuContent align="end" className="w-60">
                <DropdownMenuGroup>
                  <DropdownMenuLabel>{user ? user.name || user.email : t("menu.signedOut")}</DropdownMenuLabel>
                </DropdownMenuGroup>
                {user ? (
                  <DropdownMenuItem render={<Link href="/me" />}><UserRound /> {t("nav.myRecord")}</DropdownMenuItem>
                ) : (
                  <DropdownMenuItem render={<Link href="/auth?mode=login" />}><UserRound /> {t("nav.signin")}</DropdownMenuItem>
                )}
                {user?.role === "admin" && <DropdownMenuItem render={<Link href="/admin" />}><ShieldCheck /> {t("menu.staff")}</DropdownMenuItem>}
                <DropdownMenuSeparator />
                <DropdownMenuCheckboxItem checked={mounted && resolvedTheme === "dark"} onCheckedChange={(on) => setTheme(on ? "dark" : "light")}>
                  {t("menu.dark")}
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem checked={large} onCheckedChange={() => setLarge(toggleLargeText())}>
                  {t("menu.largeText")}
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem checked={reduced} onCheckedChange={(on) => setReduced(Boolean(on))}>
                  {t("menu.reduceMotion")}
                </DropdownMenuCheckboxItem>
                {canInstall && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => void install()}><Download /> {t("nav.install")}</DropdownMenuItem>
                  </>
                )}
                {user && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem variant="destructive" onClick={logout}><LogOut /> {t("nav.signout")}</DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>

            {!user && (
              <Button size="sm" className="hidden sm:inline-flex" render={<Link href="/auth?mode=login" />} nativeButton={false}>
                {t("nav.signin")}
              </Button>
            )}
          </div>
        </div>
        <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
      </header>

      {/* Phones: the four places that matter, as a bottom tab bar within thumb reach (spec 6.0). */}
      <nav aria-label={t("nav.primary")} className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden">
        <ul className="mx-auto grid max-w-md grid-cols-4">
          {[
            { href: "/directory", label: t("nav.directory"), Icon: Library },
            { href: "/verify", label: t("nav.verify"), Icon: ScanLine },
            { href: recordHref, label: user ? t("nav.myRecord") : t("nav.getListed"), Icon: user ? UserRound : UserRoundPlus },
          ].map(({ href, label, Icon }) => (
            <li key={href}>
              <Link
                href={href}
                aria-current={active(href) ? "page" : undefined}
                className={cn("flex h-16 flex-col items-center justify-center gap-1 text-xs text-muted-foreground", active(href) && "font-medium text-foreground shadow-[inset_0_2px_0_var(--stamp)]")}
              >
                <Icon aria-hidden className="size-5" /> {label}
              </Link>
            </li>
          ))}
          <li>
            <button type="button" onClick={() => setPaletteOpen(true)} className="flex h-16 w-full flex-col items-center justify-center gap-1 text-xs text-muted-foreground">
              <Search aria-hidden className="size-5" /> {t("nav.search")}
            </button>
          </li>
        </ul>
      </nav>
    </>
  );
}
