"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Radio } from "lucide-react";
import { AgentAvatar, AgentFeed } from "@/components/agent-feed";
import { Pipeline } from "@/components/agent-floor/pipeline";
import { AgentReplay } from "@/components/agent-floor/replay";
import { useAgentStream } from "@/hooks/use-agent-stream";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AgentInfo } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function MissionControl() {
  const { user, ready } = useAuth();
  const isAdmin = user?.role === "admin";
  const { events, connected } = useAgentStream(undefined, Boolean(isAdmin));
  const [agents, setAgents] = useState<AgentInfo[]>([]);

  useEffect(() => {
    api<AgentInfo[]>("/v1/agents/catalog", { auth: false }).then(setAgents).catch(() => {});
  }, []);

  // An agent is "active" if it emitted something in the last 20 seconds.
  const now = Date.now();
  const active = new Set(events.filter((e) => now - new Date(e.ts).getTime() < 20_000).map((e) => e.agent));
  const counts = events.reduce<Record<string, number>>((acc, e) => ({ ...acc, [e.agent]: (acc[e.agent] ?? 0) + 1 }), {});

  return (
    <div className="mx-auto max-w-7xl px-4 pb-10 pt-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-5xl md:text-7xl">Mission Control</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Every agent, every decision, as it happens. Nothing here is hidden: if an agent drops a citation it
            couldn&apos;t prove, you&apos;ll see that too.
          </p>
        </div>
        {isAdmin && (
          <span className={cn("inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm", connected ? "bg-verified-soft text-verified" : "bg-muted text-muted-foreground")}>
            <Radio aria-hidden className="size-4" /> {connected ? "Live" : "Connecting"}
          </span>
        )}
      </div>

      <div className="mt-8"><AgentReplay /></div>

      <div className="mt-6 rounded-2xl border border-border bg-card p-5">
        <p className="mb-3 text-sm font-medium">Right now</p>
        <Pipeline events={events} now={now} />
      </div>

      <div className={cn("mt-6 grid gap-6", isAdmin && "lg:grid-cols-[1fr_1.4fr]")}>
        <ul className={cn("grid content-start gap-2 sm:grid-cols-2", !isAdmin && "lg:grid-cols-3 xl:grid-cols-5")}>
          {agents.map((a) => (
            <li key={a.name} className={cn("rounded-xl border border-border bg-card p-3 transition-colors", active.has(a.name) && "border-primary/60 bg-primary/5")}>
              <div className="flex items-center gap-2">
                <AgentAvatar name={a.name} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">{a.name}</p>
                  <p className="truncate text-xs text-muted-foreground">{a.role}</p>
                </div>
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span aria-hidden className={cn("size-2 rounded-full", active.has(a.name) ? "bg-primary motion-safe:animate-pulse" : "bg-muted-foreground/30")} />
                  {active.has(a.name) ? "Working" : "Idle"}
                </span>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{a.does}</p>
              {counts[a.name] ? <p className="mt-1 text-xs tabular-nums text-muted-foreground">{counts[a.name]} recent events</p> : null}
            </li>
          ))}
        </ul>

        {isAdmin ? (
          <section className="rounded-2xl border border-border bg-card p-4" aria-label="Live agent activity">
            <AgentFeed events={[...events].reverse()} />
          </section>
        ) : (
          ready && (
            <p className="text-sm text-muted-foreground">
              The live feed of every run is for registry staff. To watch the agents work on <em>your</em> record, start from{" "}
              <Link className="text-primary underline" href="/onboard">your onboarding screen</Link>.
            </p>
          )
        )}
      </div>
    </div>
  );
}
