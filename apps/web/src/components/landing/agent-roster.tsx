"use client";

import { useEffect, useState } from "react";
import { AgentAvatar } from "@/components/agent-feed";
import { api } from "@/lib/api";
import type { AgentInfo } from "@/lib/types";

export function AgentRoster() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  useEffect(() => {
    api<AgentInfo[]>("/v1/agents/catalog", { auth: false }).then(setAgents).catch(() => {});
  }, []);
  return (
    <ul className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {agents.map((a) => (
        <li key={a.name} className="rounded-xl border border-border bg-background p-4">
          <div className="flex items-center gap-2">
            <AgentAvatar name={a.name} />
            <div>
              <p className="text-sm font-semibold">{a.name}</p>
              <p className="text-xs text-muted-foreground">
                {a.role}
                {a.kind && <> · {a.kind === "llm" ? "AI model" : a.kind === "hybrid" ? "rules + AI" : "plain code"}</>}
              </p>
            </div>
          </div>
          <p className="mt-3 text-sm">{a.does}</p>
          <p className="mt-2 text-xs text-muted-foreground">Replaces: {a.replaces}</p>
        </li>
      ))}
    </ul>
  );
}
