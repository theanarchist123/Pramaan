"use client";

import { useId, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, Quote } from "lucide-react";
import { VerificationBadge } from "@/components/verification-badge";
import { useMotionPreference } from "@/lib/motion-preference";
import type { Claim } from "@/lib/types";
import { cn } from "@/lib/utils";

const FIELD: Record<string, string> = {
  award: "Award", position: "Position", education: "Education", publication: "Publication",
  achievement: "Achievement", membership: "Membership", other: "Other",
};

/**
 * One claim and the proof behind it. The evidence is a paper slip that slides out from under the card (M-10); with reduced
 * motion it simply appears. Status is icon + text from the server enum.
 */
export function ClaimCard({ claim, isDemo }: { claim: Claim; isDemo: boolean }) {
  const [open, setOpen] = useState(false);
  const { reduced } = useMotionPreference();
  const id = useId();
  const evidence = claim.evidence.filter((e) => e.kind !== "chat");
  const slip = reduced
    ? { initial: false, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0 } }
    : { initial: { opacity: 0, y: -10 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -6 }, transition: { duration: 0.24, ease: [0.2, 0.8, 0.2, 1] as const } };

  return (
    <li className="rounded-2xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-muted-foreground">
            {FIELD[claim.field] ?? claim.field}
            {claim.year ? ` · ${claim.year}` : ""}
          </p>
          <p className="mt-0.5">{claim.value}</p>
        </div>
        <VerificationBadge status={claim.status} className="shrink-0" />
      </div>
      {evidence.length > 0 && (
        <>
          <button
            type="button"
            aria-expanded={open}
            aria-controls={id}
            onClick={() => setOpen((o) => !o)}
            className="mt-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            {open ? "Hide the evidence" : "Show the evidence"}
            <ChevronDown aria-hidden className={cn("size-3.5 transition-transform", open && "rotate-180")} />
          </button>
          <AnimatePresence initial={false}>
            {open && (
              <motion.ul id={id} {...slip} className="mt-2 space-y-2">
                {evidence.map((e) => (
                  <li key={e.id} className="rounded-sm border border-border bg-muted/60 p-3 text-sm shadow-sm">
                    <p className="flex gap-2 italic">
                      <Quote aria-hidden className="mt-0.5 size-3.5 shrink-0 opacity-60" /> {e.quote}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {e.kind === "document" ? "From an uploaded credential" : "From a public source"}
                      {e.url && !isDemo && (
                        <>
                          {" · "}
                          <a href={e.url} target="_blank" rel="noreferrer noopener" className="underline">open source</a>
                        </>
                      )}
                    </p>
                  </li>
                ))}
              </motion.ul>
            )}
          </AnimatePresence>
        </>
      )}
    </li>
  );
}
