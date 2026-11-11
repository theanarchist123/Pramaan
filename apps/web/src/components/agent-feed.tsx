"use client";

import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle, ArrowRightLeft, CheckCircle2, Flag, Search, Sparkle } from "lucide-react";
import type { AgentEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

// Each agent gets a stable colour so people learn who's who.
const AGENT_COLORS: Record<string, string> = {
  Saathi: "bg-primary text-primary-foreground",
  "Khoji-Pehle": "bg-[var(--sector-business)] text-white",
  Lipik: "bg-[oklch(0.5_0.12_200)] text-white",
  Pariksha: "bg-[oklch(0.5_0.13_300)] text-white",
  Prahari: "bg-verified text-background",
  system: "bg-muted text-muted-foreground",
};

const KIND_ICON = {
  thought: Sparkle,
  tool: Search,
  result: CheckCircle2,
  handoff: ArrowRightLeft,
  warning: AlertTriangle,
  error: AlertTriangle,
  run_finished: Flag,
} as const;

export function AgentAvatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex size-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
        AGENT_COLORS[name] ?? "bg-secondary text-secondary-foreground",
        className,
      )}
      aria-hidden="true"
    >
      {name.slice(0, 2)}
    </span>
  );
}

export function AgentFeed({
  events,
  emptyText = "Agents are idle. Their work will appear here, live.",
  compact = false,
}: {
  events: AgentEvent[];
  emptyText?: string;
  compact?: boolean;
}) {
  if (events.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">{emptyText}</p>;
  }
  return (
    <ol className="space-y-2" aria-live="polite">
      <AnimatePresence initial={false}>
        {events.map((ev, i) => {
          const Icon = KIND_ICON[ev.kind] ?? Sparkle;
          const warn = ev.kind === "warning" || ev.kind === "error";
          return (
            <motion.li
              key={`${ev.id ?? ev.ts}-${i}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className={cn(
                "flex gap-3 rounded-lg border border-transparent p-2",
                warn && "border-destructive/20 bg-destructive/5",
                ev.kind === "handoff" && "bg-muted/60",
              )}
            >
              <AgentAvatar name={ev.agent} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{ev.agent}</span>
                  <Icon className={cn("size-3", warn && "text-destructive")} aria-hidden="true" />
                  <span>{ev.kind.replace("_", " ")}</span>
                  {ev.confidence != null && (
                    <span className="ml-auto tabular-nums">{Math.round(ev.confidence * 100)}%</span>
                  )}
                </div>
                <p className={cn("text-sm leading-snug", compact && "line-clamp-2")}>{ev.message}</p>
              </div>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ol>
  );
}
