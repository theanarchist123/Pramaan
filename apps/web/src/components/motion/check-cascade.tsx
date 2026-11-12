"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { duration, ease } from "@pramaan/ui/motion";
import { useMotionPreference } from "@/lib/motion-preference";
import { cn } from "@/lib/utils";

export interface CheckStep {
  ok: boolean;
  text: string;
  sub?: string;
}

const GAP_MS = 220; // rows are at least 120 ms apart so each stays legible (spec M-04)

/**
 * M-04 check cascade: each REAL check result appears in turn, its tick drawing in. The list is an aria-live region, so a screen
 * reader hears each result once, in order. Reduced motion (OS or the in-app switch): everything is shown at once, ticks drawn.
 * The results passed in are the registry's actual answers: nothing here is a staged "verifying..." animation.
 */
export function CheckCascade({ steps, label }: { steps: CheckStep[]; label: string }) {
  const { reduced } = useMotionPreference();
  const [shown, setShown] = useState(reduced ? steps.length : 0);

  useEffect(() => {
    if (reduced) {
      setShown(steps.length);
      return;
    }
    setShown(0);
    const timers = steps.map((_, i) => window.setTimeout(() => setShown(i + 1), 250 + i * GAP_MS));
    return () => timers.forEach(window.clearTimeout);
  }, [steps, reduced]);

  return (
    <ol aria-label={label} aria-live="polite" className="space-y-3">
      {steps.slice(0, shown).map((s, i) => (
        <motion.li
          key={i}
          initial={reduced ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: duration.fast, ease: ease.enter }}
          className="flex gap-3"
        >
          <span className={cn("mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full", s.ok ? "bg-verified text-background" : "bg-destructive text-background")} aria-hidden>
            <svg viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <motion.path
                d={s.ok ? "M3.5 8.5l3 3 6-7" : "M4 4l8 8M12 4l-8 8"}
                initial={reduced ? false : { pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.18, delay: 0.05, ease: ease.ink }}
              />
            </svg>
          </span>
          <div className="min-w-0">
            <p className="text-sm">
              <span className="sr-only">{s.ok ? "Passed: " : "Failed: "}</span>
              {s.text}
            </p>
            {s.sub && <p className="mt-0.5 break-all font-mono text-[10.5px] text-muted-foreground">{s.sub}</p>}
          </div>
        </motion.li>
      ))}
    </ol>
  );
}
