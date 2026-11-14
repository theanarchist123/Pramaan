"use client";

import NumberFlow from "@number-flow/react";
import { motion } from "motion/react";
import { BadgeCheck, FileText, MessagesSquare, Share2 } from "lucide-react";
import { useMotionPreference } from "@/lib/motion-preference";
import type { Profile } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * The person's progress as four plain steps. Every step is derived from server state (claims, evidence, status, certificate),
 * never from a local timer: "Review" is only done when the server says approved.
 */
export function Journey({ profile, certCode }: { profile: Profile; certCode: string | null }) {
  const { reduced } = useMotionPreference();
  const talked = profile.claims.length > 0;
  const documented = profile.claims.some((c) => c.evidence.some((e) => e.kind === "document"));
  const approved = profile.status === "approved";
  const inReview = profile.status === "pending_review";
  const shared = Boolean(certCode);
  const steps = [
    { label: "Talk", Icon: MessagesSquare, done: talked },
    { label: "Add a document", Icon: FileText, done: documented },
    { label: approved ? "Approved" : inReview ? "With a reviewer" : "Review", Icon: BadgeCheck, done: approved },
    { label: "Certificate", Icon: Share2, done: shared },
  ];
  const doneCount = steps.filter((s) => s.done).length;
  const pct = doneCount * 25;
  const current = steps.findIndex((s) => !s.done);

  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <p className="font-display text-lg font-bold">Your profile</p>
        <NumberFlow value={pct} suffix="%" className="font-display text-lg font-bold" />
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Profile progress">
        <motion.div className="h-full rounded-full bg-[var(--brand)]" initial={false} animate={{ width: `${pct}%` }} transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 120, damping: 20 }} />
      </div>
      <ol className="mt-4 grid grid-cols-4 gap-1">
        {steps.map((s, i) => (
          <li key={s.label} className="flex flex-col items-center gap-1.5 text-center" aria-current={i === current ? "step" : undefined}>
            <span
              className={cn(
                "flex size-10 items-center justify-center rounded-full border-2 transition-colors",
                s.done ? "border-[var(--verified)] bg-[var(--verified)] text-white" : i === current ? "border-foreground bg-[var(--brand)] text-[var(--on-brand)]" : "border-border text-muted-foreground",
              )}
            >
              <s.Icon aria-hidden className="size-4.5" />
            </span>
            <span className={cn("text-xs leading-tight", i === current ? "font-bold" : "text-muted-foreground")}>
              {s.label}
              <span className="sr-only">{s.done ? " (done)" : i === current ? " (next)" : ""}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
