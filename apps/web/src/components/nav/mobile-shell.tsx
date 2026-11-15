"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { ArrowLeft, BadgeCheck, BookOpen, Code2, Download, Home, Languages, LogOut, Moon, ScanLine, Search, ShieldCheck, Sparkles, Type, UserRound, Users, Waves, MoreHorizontal, ListChecks } from "lucide-react";
import { Logo } from "@/components/logo";
import { useInstall } from "@/components/install-button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { restoreLargeText, toggleLargeText } from "@/lib/large-text";
import { useMotionPreference } from "@/lib/motion-preference";
import { haptic, isNativeApp, syncSystemBars } from "@/lib/native";
import { cn } from "@/lib/utils";

/**
 * The phone shell (below the md breakpoint): what an Android app looks like, not a shrunken website.
 *  - a solid top app bar (56dp): the mark on top-level screens, a back arrow and the screen name on inner screens;
 *  - a bottom navigation bar (Material 3): five destinations, a pill under the current one, labels always visible;
 *  - a bottom sheet for everything else: account, language, dark mode, text size, motion, the secondary pages.
 * Nothing floats over the content: the page is laid out between the two bars. Desktop keeps the floating navigation (floating-nav.tsx).
 */

const ROOTS = new Set(["/", "/directory", "/verify", "/me"]);
const TITLES: [RegExp, string][] = [
  [/^\/directory/, "Find people"],
  [/^\/verify\/.+/, "Certificate check"],
  [/^\/verify/, "Check a certificate"],
  [/^\/p\//, "Profile"],
  [/^\/transparency/, "Public log"],
  [/^\/developers/, "Developers"],
  [/^\/how-we-check/, "How we check"],
  [/^\/onboard/, "Get listed"],
  [/^\/me/, "My page"],
  [/^\/oauth/, "Allow an app"],
  [/^\/v\//, "Page"],
  [/^\/certificate/, "Certificate"],
];

function titleFor(path: string): string {
  return TITLES.find(([re]) => re.test(path))?.[1] ?? "Pramaan";
}

/** Hide the bottom bar while the on-screen keyboard is up (Android shrinks the visible area), so it never sits on top of what you are typing. */
function useKeyboardOpen(): boolean {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const check = () => setOpen(window.innerHeight - vv.height > 140);
    vv.addEventListener("resize", check);
    check();
    return () => vv.removeEventListener("resize", check);
  }, []);
  return open;
}

function Row({ icon: Icon, label, href, onClick, trailing, danger }: { icon: typeof Home; label: string; href?: string; onClick?: () => void; trailing?: React.ReactNode; danger?: boolean }) {
  const cls = cn("flex min-h-14 w-full items-center gap-4 rounded-2xl px-3 text-left text-base font-medium active:bg-muted", danger && "text-destructive");
  const inner = (
    <>
      <Icon aria-hidden className="size-6 shrink-0 text-muted-foreground" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {trailing}
    </>
  );
  return href ? (
    <Link href={href} onClick={onClick} className={cls}>{inner}</Link>
  ) : (
    <button type="button" onClick={onClick} className={cls}>{inner}</button>
  );
}

export function MobileShell() {
  const pathname = usePathname();
  const router = useRouter();
  const { user: signedIn, logout } = useAuth();
  const user = signedIn && !signedIn.is_guest ? signedIn : null;
  const { lang, setLang, t } = useI18n();
  const { resolvedTheme, setTheme } = useTheme();
  const { reduced, setReduced } = useMotionPreference();
  const { available: canInstall, install } = useInstall();
  const keyboard = useKeyboardOpen();
  const [sheet, setSheet] = useState(false);
  const [large, setLarge] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setLarge(restoreLargeText());
  }, []);

  // In the Android app the status bar takes the app bar's colour (and the right icon shade) and follows dark mode.
  useEffect(() => {
    if (mounted) syncSystemBars(resolvedTheme === "dark");
  }, [mounted, resolvedTheme]);

  const hideBottom = pathname.startsWith("/auth") || pathname.startsWith("/onboard") || pathname.startsWith("/certificate");
  const showBottom = !hideBottom && !keyboard;
  // Tell the page whether the bottom bar is taking space, so <main> can reserve exactly that much.
  useEffect(() => {
    document.documentElement.dataset.bnav = hideBottom ? "0" : "1";
  }, [hideBottom]);

  if (pathname.startsWith("/auth") || pathname.startsWith("/certificate")) return null;

  const root = ROOTS.has(pathname);
  const initials = (user?.name || user?.email || "?").trim().slice(0, 1).toUpperCase();
  const tabs = [
    { href: "/", label: t("nav.home"), Icon: Home, on: pathname === "/" },
    { href: "/directory", label: t("nav.tabFind"), Icon: Users, on: pathname.startsWith("/directory") || pathname.startsWith("/p/") },
    { href: "/verify", label: t("nav.check"), Icon: ScanLine, on: pathname.startsWith("/verify") },
    { href: user ? "/me" : "/onboard", label: user ? t("nav.myPage") : t("nav.tabJoin"), Icon: user ? UserRound : Sparkles, on: pathname.startsWith("/me") || pathname.startsWith("/onboard") },
  ];

  return (
    <div data-mobile-shell className="md:hidden">
      <header className="fixed inset-x-0 top-0 z-40 border-b border-border bg-background pt-[max(env(safe-area-inset-top),var(--safe-area-inset-top,0px))]">
        <div className="flex h-14 items-center gap-1 pl-2 pr-2">
          {root ? (
            <Link href="/" aria-label="Pramaan home" className="flex h-12 items-center rounded-full pl-2 pr-3 active:bg-muted">
              <Logo />
            </Link>
          ) : (
            <>
              <button type="button" aria-label="Back" onClick={() => { haptic("light"); if (window.history.length > 1) router.back(); else router.push("/"); }} className="inline-flex size-12 items-center justify-center rounded-full active:bg-muted">
                <ArrowLeft aria-hidden className="size-6" />
              </button>
              <h1 className="min-w-0 flex-1 truncate font-heading text-xl font-bold tracking-tight">{titleFor(pathname)}</h1>
            </>
          )}
          {root && <span className="flex-1" />}
          <button type="button" aria-label={t("nav.search")} onClick={() => { haptic("light"); window.dispatchEvent(new Event("pramaan:open-search")); }} className="inline-flex size-12 items-center justify-center rounded-full active:bg-muted">
            <Search aria-hidden className="size-6" />
          </button>
          <button type="button" aria-label={t("nav.account")} onClick={() => { haptic("light"); setSheet(true); }} className="inline-flex size-12 items-center justify-center rounded-full active:bg-muted">
            {user ? (
              <span aria-hidden className="inline-flex size-8 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">{initials}</span>
            ) : (
              <UserRound aria-hidden className="size-6" />
            )}
          </button>
        </div>
      </header>

      {showBottom && (
        <nav aria-label={t("nav.primary")} className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background pb-[max(env(safe-area-inset-bottom),var(--safe-area-inset-bottom,0px))]">
          <ul className="grid h-16 grid-cols-5">
            {tabs.map(({ href, label, Icon, on }) => (
              <li key={href} className="min-w-0">
                <Link
                  href={href}
                  aria-current={on ? "page" : undefined}
                  onClick={() => haptic("light")}
                  className="group flex h-16 flex-col items-center justify-center gap-1 px-1 outline-none"
                >
                  <span className={cn("inline-flex h-8 w-full max-w-16 items-center justify-center rounded-full transition-colors group-active:bg-muted", on && "bg-accent")}>
                    <Icon aria-hidden className="size-6" strokeWidth={on ? 2.6 : 2} />
                  </span>
                  <span className={cn("w-full truncate text-center text-xs leading-none", on ? "font-bold" : "font-medium text-muted-foreground")}>{label}</span>
                </Link>
              </li>
            ))}
            <li className="min-w-0">
              <button type="button" onClick={() => { haptic("light"); setSheet(true); }} aria-haspopup="dialog" className="group flex h-16 w-full flex-col items-center justify-center gap-1 px-1 outline-none">
                <span className="inline-flex h-8 w-full max-w-16 items-center justify-center rounded-full transition-colors group-active:bg-muted">
                  <MoreHorizontal aria-hidden className="size-6" />
                </span>
                <span className="w-full truncate text-center text-xs font-medium leading-none text-muted-foreground">{t("nav.more")}</span>
              </button>
            </li>
          </ul>
        </nav>
      )}

      <Sheet open={sheet} onOpenChange={setSheet}>
        <SheetContent side="bottom" showCloseButton={false} className="max-h-[88dvh] gap-0 overflow-y-auto rounded-t-3xl p-0 pb-[max(env(safe-area-inset-bottom),var(--safe-area-inset-bottom,0px))]">
          <div aria-hidden className="mx-auto mt-3 h-1.5 w-10 rounded-full bg-border" />
          <SheetTitle className="sr-only">{t("nav.more")}</SheetTitle>
          <SheetDescription className="sr-only">Account, language and settings</SheetDescription>
          <div className="px-3 pb-3 pt-2">
            <div className="flex items-center gap-3 px-3 py-3">
              <span aria-hidden className="inline-flex size-12 items-center justify-center rounded-full bg-primary text-lg font-bold text-primary-foreground">{user ? initials : <UserRound className="size-6" />}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-base font-bold">{user ? user.name || user.email : t("menu.signedOut")}</p>
                {user?.name && <p className="truncate text-sm text-muted-foreground">{user.email}</p>}
              </div>
              {!user && <Link href="/auth?mode=login" onClick={() => setSheet(false)} className="inline-flex h-11 items-center rounded-full bg-primary px-5 text-sm font-bold text-primary-foreground active:opacity-80">{t("nav.signin")}</Link>}
            </div>

            <nav aria-label="More pages" className="mt-1 border-t border-border pt-2">
              <Row icon={BookOpen} label="How we check" href="/how-we-check" onClick={() => setSheet(false)} />
              <Row icon={ListChecks} label={t("nav.transparency")} href="/transparency" onClick={() => setSheet(false)} />
              <Row icon={Code2} label={t("nav.developers")} href="/developers" onClick={() => setSheet(false)} />
              {user && <Row icon={UserRound} label={t("nav.myPage")} href="/me" onClick={() => setSheet(false)} />}
              {user?.role === "admin" && <Row icon={ShieldCheck} label={t("menu.staff")} href={process.env.NEXT_PUBLIC_STAFF_URL || "/staff"} onClick={() => setSheet(false)} />}
            </nav>

            <div className="mt-2 border-t border-border pt-2">
              <Row icon={Languages} label={lang === "en" ? "हिन्दी" : "English"} onClick={() => setLang(lang === "en" ? "hi" : "en")} />
              <Row icon={Moon} label={t("menu.dark")} onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")} trailing={<Switch aria-label={t("menu.dark")} checked={mounted && resolvedTheme === "dark"} />} />
              <Row icon={Type} label={t("menu.largeText")} onClick={() => setLarge(toggleLargeText())} trailing={<Switch aria-label={t("menu.largeText")} checked={large} />} />
              <Row icon={Waves} label={t("menu.reduceMotion")} onClick={() => setReduced(!reduced)} trailing={<Switch aria-label={t("menu.reduceMotion")} checked={reduced} />} />
              {canInstall && !isNativeApp() && <Row icon={Download} label={t("nav.install")} onClick={() => { setSheet(false); void install(); }} />}
            </div>

            {user && (
              <div className="mt-2 border-t border-border pt-2">
                <Row icon={LogOut} label={t("nav.signout")} onClick={() => { setSheet(false); logout(); }} danger />
              </div>
            )}
            <p className="flex items-center justify-center gap-1.5 px-3 pb-1 pt-3 text-xs text-muted-foreground"><BadgeCheck aria-hidden className="size-4" /> Every certificate can be checked by anyone</p>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
