"use client";

import { AlertCircle, Check, Circle, CircleDot, Loader2 } from "lucide-react";
import { stagesOf } from "@/lib/onboarding-stage";
import type { Profile } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Three honest stages from the server's status. Each is icon + text + colour, never colour alone. */
export function StatusStepper({ profile }: { profile: Profile }) {
  const stages = stagesOf(profile);
  const rejected = profile.status === "rejected" || profile.status === "suspended";
  return (
    <ol aria-label="Progress" className="flex flex-wrap items-start gap-x-6 gap-y-2">
      {stages.map((s, i) => {
        const bad = rejected && s.key === "decided";
        // Only the checking stage spins (work is really happening); the stage a person is simply at gets a still marker.
        const Icon = bad ? AlertCircle : s.state === "done" ? Check : s.state === "current" ? (s.key === "submitted" ? Loader2 : CircleDot) : Circle;
        return (
          <li key={s.key} aria-current={s.state === "current" ? "step" : undefined} className="flex items-start gap-2">
            <Icon
              aria-hidden
              className={cn(
                "mt-0.5 size-4 shrink-0",
                bad ? "text-destructive" : s.state === "done" ? "text-verified" : s.state === "current" ? "text-primary" : "text-muted-foreground",
                s.state === "current" && !bad && s.key === "submitted" && "motion-safe:animate-spin",
              )}
            />
            <div>
              <p className={cn("text-sm", s.state === "todo" ? "text-muted-foreground" : "font-medium")}>
                <span className="sr-only">{`Step ${i + 1}, ${s.state === "done" ? "done" : s.state === "current" ? "in progress" : "not started"}: `}</span>
                {s.label}
              </p>
              {s.note && <p className="text-xs text-muted-foreground">{s.note}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
