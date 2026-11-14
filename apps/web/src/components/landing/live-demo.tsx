"use client";

import { useEffect, useRef, useState } from "react";
import NumberFlow from "@number-flow/react";
import { motion } from "motion/react";
import { Trophy } from "lucide-react";
import { StatusTag } from "@/components/ui/status-tag";
import { useMotionPreference } from "@/lib/motion-preference";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * A scripted sample of Saathi building a profile (a FICTIONAL example, labelled as a sample). It opens at its finished state so the first
 * frame is complete, then replays. It is decoration for a sample, so it is driven by a timer; real celebrations elsewhere are never timers.
 */
const BEATS = [300, 1500, 2900, 4100, 5000];

export function LiveDemo() {
  const { t } = useI18n();
  const { reduced } = useMotionPreference();
  const [shown, setShown] = useState(5); // how many beats are visible
  const timers = useRef<number[]>([]);

  useEffect(() => {
    if (reduced) return;
    const clear = () => timers.current.forEach(window.clearTimeout);
    const play = () => {
      setShown(0);
      BEATS.forEach((ms, i) => timers.current.push(window.setTimeout(() => setShown(i + 1), ms)));
      timers.current.push(window.setTimeout(play, 12000));
    };
    timers.current.push(window.setTimeout(play, 6000));
    return clear;
  }, [reduced]);

  const pct = shown >= 5 ? 80 : shown >= 3 ? 50 : shown >= 2 ? 25 : 5;
  const step = (n: number) => cn("transition-all duration-300", shown >= n ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0");

  return (
    <div className="pop min-h-[27rem] rounded-3xl bg-card p-5 text-foreground" aria-label={t("h2.demoLabel")}>
      <p className="mb-3 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
        <span className="size-2 animate-pulse rounded-full bg-[var(--verified)]" /> {t("h2.demoTitle")}
      </p>
      <div className={cn("mb-2 max-w-[92%] rounded-2xl rounded-bl-sm bg-muted px-4 py-3 text-sm", step(1))}>{t("h2.demoQ")}</div>
      <div className={cn("mb-3 ml-auto max-w-[92%] rounded-2xl rounded-br-sm bg-primary px-4 py-3 text-sm text-primary-foreground", step(2))}>{t("h2.demoA")}</div>
      <div className={cn("mt-2 flex items-start gap-3 rounded-2xl border border-border p-3 text-sm", step(3))}>
        <Trophy aria-hidden className="mt-0.5 size-5 shrink-0 text-[var(--verified)]" />
        <div className="min-w-0">
          <p className="font-semibold">{t("h2.demoClaim")}</p>
          <StatusTag kind={shown >= 4 ? "document" : "self"} className="mt-1.5" />
        </div>
      </div>
      <p className={cn("mt-2 text-xs text-muted-foreground", step(4))}>{t("h2.demoDoc")}</p>
      <div className={cn("mt-4", step(5))}>
        <div className="mb-1.5 flex justify-between text-xs font-semibold">
          <span>{t("h2.demoMeter")}</span>
          <NumberFlow value={pct} suffix="%" />
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label={t("h2.demoMeter")} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <motion.div className="h-full rounded-full bg-[var(--brand)]" initial={false} animate={{ width: `${pct}%` }} transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 120, damping: 20 }} />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{t("h2.demoNext")}</p>
      </div>
      <p className="mt-4 text-[11px] text-muted-foreground">{t("h2.demoSample")}</p>
    </div>
  );
}
