"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { MapPin, Sparkles } from "lucide-react";
import { VerificationBadge } from "@/components/verification-badge";
import { paletteFor } from "@/lib/certificate-art";
import type { SearchHit, Summary } from "@/lib/directory-types";

export function SectorChip({ sector }: { sector: string }) {
  const c = paletteFor(sector);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground">
      <span className="size-2 rounded-full" style={{ background: c.primary }} /> {sector}
    </span>
  );
}

export function ResultCard({ hit, index = 0 }: { hit: SearchHit | (Summary & { score?: number; reasons?: string[]; claims?: SearchHit["claims"]; is_demo?: boolean }); index?: number }) {
  const reasons = "reasons" in hit ? hit.reasons ?? [] : [];
  const claims = "claims" in hit ? hit.claims ?? [] : [];
  const score = "score" in hit ? hit.score : undefined;
  return (
    <motion.li
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.05, 0.4) }}
    >
      <Link
        href={`/p/${hit.slug}`}
        className="group block h-full rounded-2xl border border-border bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-display text-lg font-semibold leading-tight group-hover:text-primary">{hit.full_name}</p>
            <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{hit.headline || hit.sector}</p>
          </div>
          {score != null && (
            <div className="shrink-0 text-right" title="How closely this person matches your question">
              <p className="font-display text-xl font-semibold tabular-nums text-primary">{Math.round(score * 100)}</p>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">match</p>
            </div>
          )}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <SectorChip sector={hit.sector} />
          {hit.state && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <MapPin className="size-3" /> {[hit.city, hit.state].filter(Boolean).join(", ")}
            </span>
          )}
          {"is_demo" in hit && hit.is_demo && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">Demo</span>
          )}
        </div>
        {reasons.length > 0 && (
          <div className="mt-3 rounded-xl bg-indigo-soft/60 p-2.5">
            <p className="mb-1 flex items-center gap-1 text-[11px] font-medium text-indigo">
              <Sparkles className="size-3" /> Why this person
            </p>
            <ul className="space-y-0.5 text-xs">
              {reasons.map((r) => (
                <li key={r} className="line-clamp-1">• {r}</li>
              ))}
            </ul>
          </div>
        )}
        {claims.length > 0 && reasons.length === 0 && (
          <ul className="mt-3 space-y-1.5">
            {claims.slice(0, 2).map((c, i) => (
              <li key={i} className="flex items-start justify-between gap-2 text-xs">
                <span className="line-clamp-1">{c.value}</span>
                <VerificationBadge status={c.status} className="shrink-0" />
              </li>
            ))}
          </ul>
        )}
      </Link>
    </motion.li>
  );
}
