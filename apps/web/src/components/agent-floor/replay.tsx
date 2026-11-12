"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import { CheckCircle2, Pause, Play, RotateCcw, UserRoundCheck } from "lucide-react";
import { AgentAvatar } from "@/components/agent-feed";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useMotionPreference } from "@/lib/motion-preference";
import { cn } from "@/lib/utils";

interface ReplayEvent { t_ms: number; agent: string; kind: string; message: string; confidence: number | null }
type Replay = { available: false } | { available: true; run_id: string; outcome: "sealed" | "with_reviewer" | "stopped"; events: ReplayEvent[] };

const STATIONS = ["Saathi", "Khoji-Pehle", "Lipik", "Pariksha", "Prahari"] as const;
const OUTCOME = {
  sealed: { icon: CheckCircle2, text: "Sealed: the rules approved it and a certificate can be issued", cls: "bg-verified-soft text-verified" },
  with_reviewer: { icon: UserRoundCheck, text: "With a reviewer: the rules did not approve it, so a person decides", cls: "bg-pending-soft text-foreground" },
  stopped: { icon: UserRoundCheck, text: "Stopped: it did not complete, so nothing was approved", cls: "bg-muted text-muted-foreground" },
} as const;

/** Real gaps between events can be minutes; play them at a watchable pace, never faster than a person can read. */
const delayBefore = (events: ReplayEvent[], i: number) => (i === 0 ? 400 : Math.min(1100, Math.max(350, events[i].t_ms - events[i - 1].t_ms)));

/**
 * "Watch it work" (spec 6.7): a recorded REAL verification run on a fictional demo profile, replayed. The token sits at the station of the agent
 * that is acting and moves along when the work is handed on. Everything shown is an event the agents actually emitted; nothing is scripted
 * here. Reduced motion: no playback, the whole run is listed and the token rests at the end.
 */
export function AgentReplay() {
  const { reduced } = useMotionPreference();
  const [data, setData] = useState<Replay | null>(null);
  const [shown, setShown] = useState(0);
  const [playing, setPlaying] = useState(false);
  const log = useRef<HTMLOListElement>(null);

  useEffect(() => {
    api<Replay>("/v1/agents/replay", { auth: false }).then(setData).catch(() => setData({ available: false }));
  }, []);

  const events = useMemo(() => (data && data.available ? data.events : []), [data]);

  // Start by itself once the run has loaded, unless the person asked for less motion.
  useEffect(() => {
    if (!events.length) return;
    if (reduced) { setShown(events.length); setPlaying(false); } else { setShown(0); setPlaying(true); }
  }, [events, reduced]);

  useEffect(() => {
    if (!playing || shown >= events.length) {
      if (shown >= events.length) setPlaying(false);
      return;
    }
    const t = setTimeout(() => setShown((n) => n + 1), delayBefore(events, shown));
    return () => clearTimeout(t);
  }, [playing, shown, events]);

  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight }); }, [shown]);

  if (!data) return <div className="h-48 animate-pulse rounded-2xl bg-muted motion-reduce:animate-none" aria-label="Loading a recorded run" />;
  if (!data.available) {
    return (
      <section aria-label="Recorded run" className="rounded-2xl border border-dashed border-border p-6 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">No recorded run to show yet</p>
        <p className="mt-1">A replay appears here after a fictional demo profile has been verified. Runs on real people are never shown publicly.</p>
      </section>
    );
  }

  const done = shown >= events.length;
  const current = events[Math.max(0, shown - 1)];
  const at = Math.max(0, STATIONS.indexOf((current?.agent ?? "Saathi") as (typeof STATIONS)[number]));
  const outcome = OUTCOME[data.outcome];
  const OutIcon = outcome.icon;

  return (
    <section aria-label="Recorded run" className="rounded-2xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-heading text-2xl font-semibold">Watch it work</h2>
          <p className="text-sm text-muted-foreground">A real run on a fictional demo profile, replayed. Every line below is something an agent actually reported.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={reduced} onClick={() => { if (done) setShown(0); setPlaying((p) => !p || done); }} aria-label={playing ? "Pause the replay" : done ? "Play the replay again" : "Play the replay"}>
            {playing ? <Pause /> : done ? <RotateCcw /> : <Play />} {playing ? "Pause" : done ? "Replay" : "Play"}
          </Button>
        </div>
      </div>

      {/* The stage: five stations in order, a token at the one that is acting. */}
      <div className="relative mt-6 px-2 pb-1">
        <div aria-hidden className="absolute left-[10%] right-[10%] top-[18px] h-0.5 rounded-full bg-border" />
        <ol className="relative grid grid-cols-5" aria-label="Stations">
          {STATIONS.map((name, i) => (
            <li key={name} className="flex flex-col items-center gap-1 text-center">
              <AgentAvatar name={name} className={cn("size-9 text-xs", i === at && shown > 0 && "ring-2 ring-primary ring-offset-2 ring-offset-card")} />
              <span className="text-xs font-medium">{name}</span>
              <span className="text-xs text-muted-foreground">{i === at && shown > 0 && !done ? "Working" : i < at || done ? "Done" : "Waiting"}</span>
            </li>
          ))}
        </ol>
        <motion.span
          aria-hidden
          layout={!reduced}
          transition={{ duration: 0.45, ease: [0.2, 0.8, 0.2, 1] }}
          className="absolute top-[11px] size-4 -translate-x-1/2 rounded-full border-2 border-background bg-primary shadow"
          style={{ left: `${10 + at * 20}%` }}
        />
      </div>

      <p className="mt-4 text-xs text-muted-foreground tabular-nums" aria-live="polite">Event {shown} of {events.length}</p>
      <ol ref={log} aria-label="What the agents reported" className="mt-2 max-h-64 space-y-1.5 overflow-y-auto rounded-xl bg-muted/50 p-3 text-sm">
        {events.slice(0, shown).map((e, i) => (
          <li key={i} className="flex gap-2">
            <span className="w-24 shrink-0 font-medium">{e.agent}</span>
            <span className={cn("min-w-0 flex-1", e.kind === "warning" || e.kind === "error" ? "text-destructive" : "")}>{e.message}</span>
            {e.confidence != null && <span className="shrink-0 text-xs text-muted-foreground tabular-nums">{Math.round(e.confidence * 100)}%</span>}
          </li>
        ))}
        {shown === 0 && <li className="text-muted-foreground">Starting...</li>}
      </ol>

      {done && (
        <p role="status" className={cn("mt-4 inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium", outcome.cls)}>
          <OutIcon aria-hidden className="size-4" /> {outcome.text}
        </p>
      )}
    </section>
  );
}
