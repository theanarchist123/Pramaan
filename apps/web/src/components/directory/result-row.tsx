"use client";

import Link from "next/link";
import { MapPin } from "lucide-react";
import { SectorChip } from "@/components/directory/result-card";
import { VerificationBadge } from "@/components/verification-badge";
import type { SearchHit } from "@/lib/directory-types";

/**
 * One ranked search result (spec 6.2, search mode): its place in the ranking, who it is, and WHY it matched, in words, so a result never
 * appears without a reason. The match score is a number with a bar, not colour alone.
 */
export function ResultRow({ hit, rank }: { hit: SearchHit; rank: number }) {
  const pct = Math.round((hit.score ?? 0) * 100);
  return (
    <li>
      <Link
        href={`/p/${hit.slug}`}
        className="group grid grid-cols-[2.25rem_1fr] gap-x-3 rounded-[var(--radius-panel)] border border-border bg-card p-4 transition-colors hover:border-primary/50 sm:grid-cols-[2.75rem_1fr_9rem]"
      >
        <span className="font-heading text-2xl font-semibold text-muted-foreground tabular-nums" aria-label={`Rank ${rank}`}>{rank}</span>
        <div className="min-w-0">
          <p className="font-heading text-xl font-semibold leading-tight group-hover:text-primary">{hit.full_name}</p>
          <p className="mt-0.5 text-sm text-muted-foreground">{hit.headline || hit.sector}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <SectorChip sector={hit.sector} />
            {hit.state && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <MapPin aria-hidden className="size-3" /> {[hit.city, hit.state].filter(Boolean).join(", ")}
              </span>
            )}
            {hit.is_demo && <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">Fictional demo</span>}
          </div>
          {hit.reasons.length > 0 && (
            <div className="mt-3 rounded-lg bg-accent px-3 py-2">
              <p className="text-xs font-medium text-accent-foreground">Why this person</p>
              <ul className="mt-1 space-y-0.5 text-sm">
                {hit.reasons.map((r) => <li key={r} className="line-clamp-2">{r}</li>)}
              </ul>
            </div>
          )}
          {hit.claims.length > 0 && hit.reasons.length === 0 && (
            <ul className="mt-3 space-y-1.5">
              {hit.claims.slice(0, 2).map((c, i) => (
                <li key={i} className="flex items-start justify-between gap-2 text-sm">
                  <span className="line-clamp-1">{c.value}</span>
                  <VerificationBadge status={c.status} className="shrink-0" />
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="col-span-2 mt-3 sm:col-span-1 sm:mt-0" title="How closely this person matches your question">
          <p className="text-xs text-muted-foreground">Match</p>
          <p className="font-heading text-2xl font-semibold tabular-nums text-primary">{pct}</p>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
            <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </Link>
    </li>
  );
}
