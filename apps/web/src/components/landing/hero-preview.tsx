"use client";

import { motion } from "motion/react";
import { VerificationBadge } from "@/components/verification-badge";
import { AgentAvatar } from "@/components/agent-feed";

/** Illustrative mock of the split-screen onboarding (sample data, clearly labelled). */
export function HeroPreview() {
  const rows = [
    { field: "Award", value: "Sagar Samman for marine research (2024)", status: "document" as const },
    { field: "Position", value: "Principal Scientist, coastal ecology lab", status: "web" as const },
    { field: "Education", value: "PhD, Marine Biology", status: "self" as const },
  ];
  return (
    <div className="relative" aria-label="Example of the onboarding screen">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="rounded-3xl border border-border bg-card p-5 shadow-xl shadow-primary/5"
      >
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Example profile · sample data</span>
          <span className="rounded-full bg-muted px-2 py-0.5">Live</span>
        </div>
        <div className="mt-4 flex gap-3">
          <AgentAvatar name="Saathi" />
          <p className="rounded-2xl rounded-tl-sm bg-muted px-3 py-2 text-sm">
            Which award are you most proud of, and in which year?
          </p>
        </div>
        <div className="mt-3 flex justify-end">
          <p className="max-w-[80%] rounded-2xl rounded-tr-sm bg-primary px-3 py-2 text-sm text-primary-foreground">
            मुझे 2024 में समुद्री शोध के लिए सागर सम्मान मिला था।
          </p>
        </div>
        <div className="mt-5 rounded-2xl border border-border bg-background p-4">
          <p className="font-display text-xl font-semibold">Dr. Meera Iyer</p>
          <p className="text-sm text-muted-foreground">Marine scientist · Kochi, Kerala</p>
          <ul className="mt-4 space-y-2.5">
            {rows.map((r, i) => (
              <motion.li
                key={r.field}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.5 + i * 0.25 }}
                className="flex items-start justify-between gap-3"
              >
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{r.field}</p>
                  <p className="text-sm">{r.value}</p>
                </div>
                <VerificationBadge status={r.status} />
              </motion.li>
            ))}
          </ul>
        </div>
      </motion.div>
    </div>
  );
}
