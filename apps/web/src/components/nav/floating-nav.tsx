"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { useTheme } from "next-themes";
import { Download, Languages, LogOut, MoreHorizontal, Search, ScanLine, ShieldCheck, Sparkles, UserRound, Users } from "lucide-react";
import { Logo } from "@/components/logo";
import { CommandPalette } from "@/components/command-palette";
import { useInstall } from "@/components/install-button";
import {
  DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth";
import { HINDI_UI_ENABLED, useI18n } from "@/lib/i18n";
import { restoreLargeText, toggleLargeText } from "@/lib/large-text";
import { useMotionPreference } from "@/lib/motion-preference";
import { cn } from "@/lib/utils";
import { toneClass, useNavTone } from "./use-nav-tone";

/** A piece with no fill: only a hairline in the current text colour, so it floats over any section without a bar behind it. */
const chip =
  "pointer-events-auto inline-flex h-10 items-center gap-2 whitespace-nowrap rounded-full border border-current/25 px-3.5 text-sm font-semibold transition-colors hover:border-current/60 focus-visible:outline-2 focus-visible:outline-offset-2";

export function FloatingNav() {
  const pathname = usePathname();
  const { user: signedIn, logout } = useAuth();
  const user = signedIn && !signedIn.is_guest ? signedIn : null; // a guest has no account yet, so the menu treats them as signed out
  const { lang, setLang, t } = useI18n();
  const { resolvedTheme, setTheme } = useTheme();
  const { reduced, setReduced } = useMotionPreference();
  const { available: canInstall, install } = useInstall();
  const tones = useNavTone();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [large, setLarge] = useState(false);
  const lastY = useRef(0);

  useEffect(() => {
    setMounted(true);
    setLarge(restoreLargeText());
    // The phone shell (mobile-shell.tsx) has its own search button; it asks this palette to open.
    const openSearch = () => setPaletteOpen(true);
    window.addEventListener("pramaan:open-search", openSearch);
    // Hide while reading downwards; return on any upward scroll, near the top, or near the page end.
    const onScroll = () => {
      const y = window.scrollY;
      const nearEnd = window.innerHeight + y >= document.documentElement.scrollHeight - 120;
      if (y < lastY.current - 4 || y < 120 || nearEnd) setHidden(false);
      else if (y > lastY.current + 4) setHidden(true);
      lastY.current = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("pramaan:open-search", openSearch);
    };
  }, []);

  const active = (href: string) => pathname === href || pathname.startsWith(`${href}/`);
  const initials = (user?.name || user?.email || "?").trim().slice(0, 1).toUpperCase();
  const slide = (offset: number) => ({ y: hidden ? offset : 0, opacity: hidden ? 0 : 1 });
  const slideTransition = reduced ? { duration: 0 } : { type: "spring" as const, stiffness: 380, damping: 32 };

  const DOCK = [
    { href: "/directory", label: t("nav.find"), Icon: Users },
    { href: user ? "/me" : "/onboard", label: user ? t("nav.myPage") : t("nav.getListed"), Icon: user ? UserRound : Sparkles },
    { href: "/verify", label: t("nav.check"), Icon: ScanLine },
  ];

  // The sign-in / create-account page is its own screen: no navigation on it.
  if (pathname.startsWith("/auth")) return null;

  const tabList = (compact: boolean) => (
    <ul className="flex items-center gap-1.5">
      {DOCK.map(({ href, label, Icon }) => (
        <li key={href}>
          <Link href={href} aria-current={active(href) ? "page" : undefined} className={cn(chip, active(href) && "border-2 border-current font-bold")}>
            <Icon aria-hidden className="size-4" />
            <span className={cn(compact && !active(href) && "max-sm:sr-only")}>{label}</span>
          </Link>
        </li>
      ))}
      <li>
        <DropdownMenu>
          <DropdownMenuTrigger render={<button type="button" aria-label={t("nav.more")} className={cn(chip, "px-3")} />}>
            <MoreHorizontal aria-hidden className="size-5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuItem render={<Link href="/how-we-check" />}>How we check</DropdownMenuItem>
            <DropdownMenuItem render={<Link href="/transparency" />}>{t("nav.transparency")}</DropdownMenuItem>
            <DropdownMenuItem render={<Link href="/developers" />}>{t("nav.developers")}</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </li>
    </ul>
  );

  return (
    <header data-floating-nav className="hidden md:block">
      {/* Top-left: the mark. */}
      <motion.div
        initial={false}
        animate={slide(-24)}
        transition={slideTransition}
        className={cn("pointer-events-none fixed left-0 top-[env(safe-area-inset-top)] z-40 px-4 pt-3", toneClass(tones.logo))}
      >
        <Link href="/" aria-label="Pramaan home" className="pointer-events-auto inline-flex rounded-full focus-visible:outline-2 focus-visible:outline-offset-4">
          <Logo />
        </Link>
      </motion.div>

      {/* Top-right: search and account. */}
      <motion.div
        initial={false}
        animate={slide(-24)}
        transition={slideTransition}
        className={cn("pointer-events-none fixed right-0 top-[env(safe-area-inset-top)] z-40 flex items-center gap-2 px-4 pt-3", toneClass(tones.actions))}
      >
        <nav aria-label={t("nav.primary")} className="mr-1 hidden md:block">{tabList(false)}</nav>
        <button type="button" className={chip} onClick={() => setPaletteOpen(true)}>
          <Search aria-hidden className="size-4" />
          <span className="max-sm:sr-only">{t("nav.search")}</span>
          <kbd aria-hidden className="hidden rounded border border-current/25 px-1.5 text-[10px] lg:inline">Ctrl K</kbd>
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger render={<button type="button" aria-label={t("nav.account")} className={cn(chip, "px-2.5")} />}>
            {user ? (
              <span aria-hidden className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">{initials}</span>
            ) : (
              <>
                <UserRound aria-hidden className="size-4" />
                <span className="hidden sm:inline">{t("nav.signin")}</span>
              </>
            )}
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <DropdownMenuGroup>
              <DropdownMenuLabel>{user ? user.name || user.email : t("menu.signedOut")}</DropdownMenuLabel>
            </DropdownMenuGroup>
            {user ? (
              <DropdownMenuItem render={<Link href="/me" />}><UserRound /> {t("nav.myPage")}</DropdownMenuItem>
            ) : (
              <DropdownMenuItem render={<Link href="/auth?mode=login" />}><UserRound /> {t("nav.signin")}</DropdownMenuItem>
            )}
            {user?.role === "admin" && (
              <DropdownMenuItem render={<a href={process.env.NEXT_PUBLIC_STAFF_URL || "/staff"} />}><ShieldCheck /> {t("menu.staff")}</DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            {HINDI_UI_ENABLED && (
              <DropdownMenuItem onClick={() => setLang(lang === "en" ? "hi" : "en")} lang={lang === "en" ? "hi" : "en"}>
                <Languages /> {lang === "en" ? "हिन्दी" : "English"}
              </DropdownMenuItem>
            )}
            <DropdownMenuCheckboxItem checked={mounted && resolvedTheme === "dark"} onCheckedChange={(on) => setTheme(on ? "dark" : "light")}>
              {t("menu.dark")}
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem checked={large} onCheckedChange={() => setLarge(toggleLargeText())}>
              {t("menu.largeText")}
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem checked={reduced} onCheckedChange={(on) => setReduced(Boolean(on))}>
              {t("menu.reduceMotion")}
            </DropdownMenuCheckboxItem>
            {canInstall && <DropdownMenuItem onClick={() => void install()}><Download /> {t("nav.install")}</DropdownMenuItem>}
            {user && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onClick={logout}><LogOut /> {t("nav.signout")}</DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </motion.div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </header>
  );
}
