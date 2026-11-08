"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, ExternalLink, MapPin, Quote } from "lucide-react";
import { ConfidenceMeter, VerificationBadge } from "@/components/verification-badge";
import { api } from "@/lib/api";
import type { Claim, Profile } from "@/lib/types";
import { cn } from "@/lib/utils";

const FIELD_LABEL: Record<string, string> = {
  award: "Award", position: "Position", education: "Education", publication: "Publication",
  achievement: "Achievement", membership: "Membership", other: "Other",
};

const STATUS_COPY: Record<Profile["status"], { label: string; cls: string }> = {
  draft: { label: "Draft", cls: "bg-muted text-muted-foreground" },
  pending_review: { label: "Under review", cls: "bg-pending-soft text-foreground" },
  approved: { label: "Verified", cls: "bg-verified-soft text-verified" },
  rejected: { label: "Needs changes", cls: "bg-destructive/10 text-destructive" },
};

export function completeness(p: Profile): { pct: number; missing: string[] } {
  const checks: [boolean, string][] = [
    [p.full_name !== "New Profile", "name"],
    [Boolean(p.sector), "field"],
    [Boolean(p.state), "state"],
    [p.claims.length > 0, "an achievement"],
    [Boolean(p.headline || p.bio), "a short intro"],
  ];
  const done = checks.filter(([ok]) => ok).length;
  return { pct: Math.round((done / checks.length) * 100), missing: checks.filter(([ok]) => !ok).map(([, m]) => m) };
}

function ClaimRow({ claim }: { claim: Claim }) {
  const [open, setOpen] = useState(false);
  const evidence = claim.evidence.filter((e) => e.kind !== "chat" || claim.status === "self");
  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: 16, backgroundColor: "color-mix(in oklch, var(--primary) 14%, transparent)" }}
      animate={{ opacity: 1, x: 0, backgroundColor: "rgba(0,0,0,0)" }}
      transition={{ duration: 0.6 }}
      className="rounded-xl border border-border p-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
            {FIELD_LABEL[claim.field] ?? claim.field}
            {claim.year ? ` · ${claim.year}` : ""}
          </p>
          <p className="mt-0.5 text-sm leading-snug">{claim.value}</p>
        </div>
        <VerificationBadge status={claim.status} className="shrink-0" />
      </div>
      <div className="mt-2 flex items-center justify-between">
        <ConfidenceMeter value={claim.confidence} />
        {evidence.length > 0 && (
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            aria-expanded={open}
          >
            Evidence ({evidence.length}) <ChevronDown className={cn("size-3 transition-transform", open && "rotate-180")} />
          </button>
        )}
      </div>
      <AnimatePresence>
        {open && (
          <motion.ul
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-2 space-y-2 overflow-hidden"
          >
            {evidence.map((e) => (
              <li key={e.id} className="rounded-lg bg-muted/60 p-2.5 text-xs">
                <p className="flex gap-1.5 italic">
                  <Quote className="size-3 shrink-0 translate-y-0.5 opacity-60" /> {e.quote}
                </p>
                <p className="mt-1 flex items-center gap-1 text-muted-foreground">
                  {e.kind === "web" ? "Public source" : e.kind === "document" ? "Your document" : "You said"}
                  {e.url && (
                    <a href={e.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline-offset-2 hover:underline">
                      · open <ExternalLink className="size-3" />
                    </a>
                  )}
                </p>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </motion.li>
  );
}

export function ProfilePanel({ profile }: { profile: Profile }) {
  const [defs, setDefs] = useState<{ key: string; label: string; type: string }[]>([]);
  useEffect(() => {
    api<{ key: string; label: string; type: string }[]>("/v1/fields", { auth: false }).then(setDefs).catch(() => {});
  }, []);
  const { pct, missing } = completeness(profile);
  const filled = defs.filter((d) => profile.custom?.[d.key] != null);
  const named = profile.full_name !== "New Profile";
  const status = STATUS_COPY[profile.status];
  const verified = profile.claims.filter((c) => c.status !== "self").length;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <motion.h2 key={profile.full_name} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={cn("text-3xl font-semibold", !named && "text-muted-foreground/60")}>
            {named ? profile.full_name : "Your name"}
          </motion.h2>
          <p className="mt-1 text-muted-foreground">{profile.headline || (profile.sector ? `${profile.sector}` : "Your field will appear here")}</p>
          {(profile.city || profile.state) && (
            <p className="mt-1 inline-flex items-center gap-1 text-sm text-muted-foreground">
              <MapPin className="size-3.5" /> {[profile.city, profile.state].filter(Boolean).join(", ")}
            </p>
          )}
        </div>
        <span className={cn("shrink-0 rounded-full px-2.5 py-1 text-xs font-medium", status.cls)}>{status.label}</span>
      </div>

      <div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Profile {pct}% complete{missing.length ? ` — still need ${missing.join(", ")}` : ""}</span>
          <span>{verified}/{profile.claims.length} verified</span>
        </div>
        <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
          <motion.div className="h-full rounded-full bg-primary" animate={{ width: `${pct}%` }} transition={{ duration: 0.6 }} />
        </div>
      </div>

      {(profile.sector || profile.institutions.length > 0 || profile.languages.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {profile.sector && <span className="rounded-full bg-indigo-soft px-2.5 py-1 text-xs text-indigo">{profile.sector}</span>}
          {profile.institutions.map((i) => (
            <span key={i} className="rounded-full bg-secondary px-2.5 py-1 text-xs">{i}</span>
          ))}
          {profile.languages.map((l) => (
            <span key={l} className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground">{l}</span>
          ))}
        </div>
      )}

      {profile.bio && <p className="text-[15px] leading-relaxed">{profile.bio}</p>}

      {defs.length > 0 && (
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {defs.map((d) => {
            const v = profile.custom?.[d.key];
            return (
              <div key={d.key}>
                <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{d.label}</dt>
                <dd className={cn("text-sm", v == null && "text-muted-foreground/60")}>
                  {v == null ? "— Saathi will ask" : Array.isArray(v) ? v.join(", ") : String(v)}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
      {filled.length > 0 && <span className="sr-only">{filled.length} extra field(s) filled</span>}

      <div>
        <h3 className="mb-2 text-sm font-semibold">Achievements & claims</h3>
        {profile.claims.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
            As you talk, each achievement appears here — first as <em>self-claimed</em>, then upgraded as agents find proof.
          </p>
        ) : (
          <ul className="space-y-2">
            <AnimatePresence initial={false}>
              {profile.claims.map((c) => (
                <ClaimRow key={c.id} claim={c} />
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </div>
  );
}
