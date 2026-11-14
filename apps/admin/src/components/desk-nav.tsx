"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { CommandBar } from "@/components/command-bar";
import { Icon } from "@/components/ui";

const WEB = process.env.NEXT_PUBLIC_WEB_URL ?? ""; // same origin as the public site

// `needs`: shown only to people holding at least one of these permissions (the API enforces the same rules; this just stops offering pages that would be refused).
const SYSTEM: { href: string; label: string; hint: string; needs?: string[] }[] = [
  { href: "/registry", label: "Registry and compliance", hint: "suspend, restore, consents", needs: ["profile.suspend", "consent.read"] },
  { href: "/builder", label: "Views and migrations", hint: "features the builder proposed" },
  { href: "/calibration", label: "Calibration", hint: "reviews against the auditor", needs: ["agent_run.read"] },
  { href: "/incidents", label: "Incidents", hint: "problems the watcher found", needs: ["audit.read"] },
  { href: "/images", label: "Photographs", hint: "approve field photos" },
  { href: "/security", label: "Security", hint: "your sign-in protection" },
];
const TABS = [
  { href: "/", label: "Review" },
  { href: "/people", label: "People" },
  { href: "/followups", label: "Follow-ups" },
];

function ThemeToggle() {
  const [dark, setDark] = useState(true);
  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);
  function flip() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem("desk-theme", next ? "dark" : "light"); } catch { /* private window: the choice just lasts for this visit */ }
  }
  return (
    <button type="button" className="desk-icon" onClick={flip} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} title={dark ? "Light theme" : "Dark theme"}>
      <Icon name={dark ? "sun" : "moon"} size={18} />
    </button>
  );
}

/** The Desk's navigation: transparent pieces floating at the top (no bar, no fill), like the public site. Ctrl K reaches everything. */
export function DeskNav() {
  const path = usePathname();
  const router = useRouter();
  const [perms, setPerms] = useState<string[] | null>(null);
  useEffect(() => {
    if (path === "/login") return;
    api<{ permissions: string[] }>("/v1/admin/me/permissions").then((r) => setPerms(r.permissions)).catch(() => setPerms([]));
  }, [path]);
  const offered = SYSTEM.filter((x) => !x.needs || (perms ?? []).some((p) => x.needs!.includes(p)));
  async function signOut() {
    await api("/v1/admin/auth/logout", { method: "POST" }).catch(() => {});
    router.push("/login");
  }
  const here = (href: string) => (href === "/" ? path === "/" || path.startsWith("/case") : path === href || path.startsWith(`${href}/`));
  if (path === "/login") return null; // the sign-in screen has its own header

  return (
    <header className="desk-nav">
      <Link href="/" className="desk-logo" aria-label="Desk home">
        <i><svg viewBox="0 0 40 40" aria-hidden="true"><path d="M8 21l8 8L33 11" fill="none" stroke="#14152B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" /></svg></i>
        Pramaan <small>Desk</small>
      </Link>
      {(
        <nav aria-label="Desk" style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {TABS.map((t) => (
            <Link key={t.href} href={t.href} className="desk-tab" aria-current={here(t.href) ? "page" : undefined}>{t.label}</Link>
          ))}
          <details key={path} className="desk-more">
            <summary aria-label="System">System ▾</summary>
            <div className="desk-menu">
              {offered.map((s) => (
                <Link key={s.href} href={s.href}>{s.label}<small>{s.hint}</small></Link>
              ))}
              <a href={`${WEB}/mission-control`} target="_blank" rel="noreferrer">Mission Control<small>live agents (public site)</small></a>
            </div>
          </details>
          <CommandBar />
          <ThemeToggle />
          <button type="button" className="desk-signout" onClick={signOut}>Sign out</button>
        </nav>
      )}
    </header>
  );
}
