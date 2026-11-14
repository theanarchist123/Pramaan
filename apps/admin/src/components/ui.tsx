import type { ReactNode } from "react";
import { type Tone } from "@/lib/labels";

type IconName = "check" | "alert" | "clock" | "user" | "search" | "mail" | "shield" | "key" | "inbox" | "eye" | "eyeoff" | "copy" | "sun" | "moon" | "flag" | "file" | "arrow";

const PATHS: Record<IconName, ReactNode> = {
  check: <path d="M5 12.5l4.2 4.2L19 7" />,
  alert: <><path d="M12 4l9 16H3L12 4z" /><path d="M12 10v4M12 17.2v.1" /></>,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  user: <><circle cx="12" cy="8.5" r="3.5" /><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5" /></>,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4.5 4.5" /></>,
  mail: <><rect x="3.5" y="5.5" width="17" height="13" rx="2.5" /><path d="M4 7.5l8 6 8-6" /></>,
  shield: <><path d="M12 3.5l7 2.8v5.4c0 4.4-2.9 7.5-7 8.8-4.1-1.3-7-4.4-7-8.8V6.3l7-2.8z" /><path d="M9 12l2.2 2.2L15.5 10" /></>,
  key: <><circle cx="8" cy="14" r="3.5" /><path d="M10.5 11.5L19 3M16 6l2.5 2.5M13.5 8.5L16 11" /></>,
  inbox: <><path d="M4 13l2.5-7.5h11L20 13v5.5H4V13z" /><path d="M4 13h4.5l1 2.5h5l1-2.5H20" /></>,
  eye: <><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="2.8" /></>,
  eyeoff: <><path d="M3 3l18 18M10.2 5.7A9 9 0 0112 5.5c6 0 9.5 6.5 9.5 6.5a16 16 0 01-3 3.8M6.5 7.2A15.7 15.7 0 002.5 12S6 18.5 12 18.5a9 9 0 003.6-.8M9.9 9.9a2.8 2.8 0 003.9 3.9" /></>,
  copy: <><rect x="8.5" y="8.5" width="11" height="11" rx="2.5" /><path d="M15.5 8.5v-2a2 2 0 00-2-2h-7a2 2 0 00-2 2v7a2 2 0 002 2h2" /></>,
  sun: <><circle cx="12" cy="12" r="3.8" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4" /></>,
  moon: <path d="M19.5 14.5A7.5 7.5 0 019.5 4.5a7.5 7.5 0 1010 10z" />,
  flag: <><path d="M6 21V4" /><path d="M6 5h11l-2 4 2 4H6" /></>,
  file: <><path d="M7 3.5h7l4 4v13H7z" /><path d="M14 3.5v4h4M9.5 12h5M9.5 15.5h5" /></>,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg className="ic" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[name]}
    </svg>
  );
}

const TONE_ICON: Record<Tone, IconName> = { ok: "check", warn: "clock", bad: "alert", info: "shield", quiet: "clock" };

/** A status: icon + words + colour (never colour alone). */
export function Pill({ tone = "quiet", icon, children }: { tone?: Tone; icon?: IconName | false; children: ReactNode }) {
  const name = icon === false ? null : icon ?? TONE_ICON[tone];
  return <span className={`pill pill-${tone}`}>{name && <Icon name={name} size={14} />}{children}</span>;
}

export function PageHead({ eyebrow, title, lead, actions }: { eyebrow?: string; title: string; lead?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <div className="grow">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {lead && <p className="lead">{lead}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </header>
  );
}

export function Stat({ n, label, tone = "quiet", icon, unit }: { n: ReactNode; label: string; tone?: Tone; icon: IconName; unit?: string }) {
  return (
    <div className={`stat stat-${tone}`}>
      <span className="stat-ic"><Icon name={icon} size={20} /></span>
      <b>{n}{unit && <small>{unit}</small>}</b>
      <span>{label}</span>
    </div>
  );
}

export function Avatar({ name, tile, size = 46 }: { name: string; tile: number; size?: number }) {
  const n = name.replace(/^(dr|prof|shri|smt)\.?\s+/i, "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => Array.from(w)[0]).join("").toUpperCase() || "?";
  return (
    <span className="av" aria-hidden style={{ width: size, height: size, background: `var(--tile${tile})`, color: `var(--tile${tile}i)` }}>{n}</span>
  );
}
