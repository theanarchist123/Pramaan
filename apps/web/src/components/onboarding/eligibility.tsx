"use client";

import { useEffect, useState } from "react";
import { Check, Circle } from "lucide-react";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";

interface Result {
  criteria: { id: string; label: string; how: string; met: boolean }[];
  met_count: number;
  needed: number;
  eligible: boolean;
}

/** "Who qualifies", from the server's fixed rules. Informational: reviewers still decide, and nothing here approves anyone. */
export function Eligibility({ profile }: { profile: Profile }) {
  const [r, setR] = useState<Result | null>(null);
  const signature = profile.claims.map((c) => `${c.id}:${c.status}`).join(",");

  useEffect(() => {
    api<Result>(`/v1/onboarding/${profile.id}/eligibility`).then(setR).catch(() => setR(null));
  }, [profile.id, signature]);

  if (!r) return null;
  return (
    <section className="rounded-2xl border border-border bg-card p-4" aria-labelledby="elig-h">
      <h2 id="elig-h" className="text-lg font-bold">Who qualifies</h2>
      <p className="mt-0.5 text-sm text-muted-foreground">
        Meet {r.needed} of {r.criteria.length}. Only claims backed by evidence count. {r.eligible ? "You meet the bar. A reviewer still makes the final call." : `You meet ${r.met_count} so far.`}
      </p>
      <ul className="mt-3 space-y-2">
        {r.criteria.map((c) => (
          <li key={c.id} className="flex items-start gap-2.5 text-sm">
            {c.met ? <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-[var(--verified)]" /> : <Circle aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />}
            <span>
              <b>{c.label}</b> <span className="text-muted-foreground">{c.how}</span>
              <span className="sr-only">{c.met ? " (met)" : " (not yet)"}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
