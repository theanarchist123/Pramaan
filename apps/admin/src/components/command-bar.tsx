"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const WEB = process.env.NEXT_PUBLIC_WEB_URL ?? ""; // same origin: the public site and /staff share one address

interface Dest { label: string; hint: string; href: string; external?: boolean; group: "Desk" | "System" }

const DESTS: Dest[] = [
  { label: "Review", hint: "cases waiting for a person", href: "/", group: "Desk" },
  { label: "People", hint: "search the registry in plain words", href: "/people", group: "Desk" },
  { label: "Follow-ups", hint: "drafted messages to approve", href: "/followups", group: "Desk" },
  { label: "Registry and compliance", hint: "suspend or restore, consents", href: "/registry", group: "System" },
  { label: "Views and migrations", hint: "features the builder proposed", href: "/builder", group: "System" },
  { label: "Calibration", hint: "how reviews compare with the auditor", href: "/calibration", group: "System" },
  { label: "Incidents", hint: "problems the watcher found", href: "/incidents", group: "System" },
  { label: "Photographs", hint: "approve field photos", href: "/images", group: "System" },
  { label: "Security", hint: "your sign-in protection", href: "/security", group: "System" },
  { label: "Mission Control", hint: "live view of the agents (opens the public site)", href: `${WEB}/mission-control`, external: true, group: "System" },
];

/** The Desk has no sidebar: Ctrl/Cmd+K is the navigation. A faint hint chip floats top-right so it can be found. */
export function CommandBar() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  const list = useMemo(() => DESTS.filter((d) => `${d.label} ${d.hint}`.toLowerCase().includes(q.trim().toLowerCase())), [q]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (open) {
      setQ("");
      setI(0);
      setTimeout(() => input.current?.focus(), 0);
    }
  }, [open]);

  const go = (d: Dest) => {
    setOpen(false);
    if (d.external) window.open(d.href, "_blank", "noopener");
    else router.push(d.href);
  };

  return (
    <>
      <button type="button" className="cmdk-chip" onClick={() => setOpen(true)} aria-label="Go anywhere (Ctrl K)">
        Go anywhere <kbd>Ctrl K</kbd>
      </button>
      {open && (
        <div className="cmdk-scrim" onMouseDown={() => setOpen(false)}>
          <div className="cmdk" role="dialog" aria-modal="true" aria-label="Go anywhere" onMouseDown={(e) => e.stopPropagation()}>
            <input
              ref={input}
              value={q}
              onChange={(e) => { setQ(e.target.value); setI(0); }}
              placeholder="Go to…"
              aria-label="Go to"
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") { e.preventDefault(); setI((n) => Math.min(n + 1, list.length - 1)); }
                else if (e.key === "ArrowUp") { e.preventDefault(); setI((n) => Math.max(n - 1, 0)); }
                else if (e.key === "Enter" && list[i]) go(list[i]);
              }}
            />
            <ul role="listbox">
              {list.length === 0 && <li className="muted" style={{ padding: 12 }}>No match.</li>}
              {list.map((d, n) => (
                <li key={d.href} role="option" aria-selected={n === i} className={n === i ? "on" : ""} onMouseEnter={() => setI(n)} onClick={() => go(d)}>
                  <span>{d.label}</span>
                  <span className="muted">{d.hint}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}
