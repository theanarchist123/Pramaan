"use client";

import { useEffect, useState } from "react";
import { BadgeCheck, CalendarPlus, ScrollText } from "lucide-react";
import { api } from "@/lib/api";

interface Proof { real_people: number; real_certificates: number; joined_this_month: number }

/** Three real numbers from the server. Hidden until at least three real members exist (never counts the fictional demos), so it can never look padded or empty. */
export const MIN_REAL_PEOPLE = 3;

export function ProofStrip() {
  const [p, setP] = useState<Proof | null>(null);
  useEffect(() => {
    api<Proof>("/v1/stats/proof", { auth: false }).then(setP).catch(() => setP(null));
  }, []);
  if (!p || p.real_people < MIN_REAL_PEOPLE) return null;
  const items = [
    { Icon: BadgeCheck, n: p.real_people, label: p.real_people === 1 ? "person verified" : "people verified" },
    { Icon: ScrollText, n: p.real_certificates, label: p.real_certificates === 1 ? "certificate you can check" : "certificates you can check" },
    ...(p.joined_this_month > 0 ? [{ Icon: CalendarPlus, n: p.joined_this_month, label: "joined this month" }] : []),
  ];
  return (
    <section aria-label="The registry in numbers" className="border-b border-border">
      <ul className="mx-auto flex max-w-7xl flex-wrap gap-x-10 gap-y-3 px-4 py-5">
        {items.map(({ Icon, n, label }) => (
          <li key={label} className="flex items-center gap-2.5">
            <Icon aria-hidden className="size-5 shrink-0 text-[var(--verified)]" />
            <span><b className="font-display text-2xl tabular-nums">{n}</b> <span className="text-muted-foreground">{label}</span></span>
          </li>
        ))}
      </ul>
    </section>
  );
}
