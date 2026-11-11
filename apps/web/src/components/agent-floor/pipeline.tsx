"use client";

import { motion } from "motion/react";
import { AgentAvatar } from "@/components/agent-feed";
import { useMotionPreference } from "@/lib/motion-preference";
import type { AgentEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The verification order the agents hand work along. */
const ORDER = ["Saathi", "Khoji-Pehle", "Lipik", "Pariksha", "Prahari"] as const;
const RECENT_MS = 20_000;

/**
 * M-11 handoff line: stations in workflow order. A line between two stations lights up and a dot travels along it ONLY when a real
 * `handoff` event came from the earlier agent in the last 20 seconds; nothing moves on a timer. Reduced motion: the line is simply
 * drawn in the active colour, no travelling dot. A station that is working also says "Working" in text.
 */
export function Pipeline({ events, now }: { events: AgentEvent[]; now: number }) {
  const { reduced } = useMotionPreference();
  const recent = events.filter((e) => now - new Date(e.ts).getTime() < RECENT_MS);
  const working = new Set(recent.map((e) => e.agent));
  const handedOff = new Set(recent.filter((e) => e.kind === "handoff").map((e) => e.agent));

  return (
    <ol aria-label="Order of work" className="flex flex-wrap items-center gap-y-3">
      {ORDER.map((name, i) => {
        const line = handedOff.has(name);
        return (
          <li key={name} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <AgentAvatar name={name} className={cn("size-9 text-xs", working.has(name) && "ring-2 ring-primary ring-offset-2 ring-offset-background")} />
              <span className="text-xs font-medium">{name}</span>
              <span className="text-xs text-muted-foreground">{working.has(name) ? "Working" : "Idle"}</span>
            </div>
            {i < ORDER.length - 1 && (
              <span aria-hidden className="relative mx-2 mb-8 h-0.5 w-10 overflow-hidden rounded-full bg-border sm:w-16">
                <span className={cn("absolute inset-0 rounded-full bg-primary transition-opacity", line ? "opacity-100" : "opacity-0")} />
                {line && !reduced && (
                  <motion.span
                    className="absolute top-1/2 size-1.5 -translate-y-1/2 rounded-full bg-background"
                    initial={{ x: -6 }}
                    animate={{ x: 64 }}
                    transition={{ duration: 0.9, repeat: 2, ease: "easeInOut" }}
                  />
                )}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
