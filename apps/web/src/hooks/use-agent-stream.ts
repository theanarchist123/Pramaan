"use client";

import { useEffect, useRef, useState } from "react";
import { streamUrl } from "@/lib/api";
import type { AgentEvent } from "@/lib/types";

/** Live agent events over SSE. Pass a profileId to watch one profile (owners), or none (admins). */
export function useAgentStream(profileId: string | undefined, enabled = true) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const seen = useRef(new Set<string>());

  useEffect(() => {
    if (!enabled) return;
    const url = streamUrl(profileId);
    if (!url) return;
    const es = new EventSource(url);

    const push = (raw: MessageEvent) => {
      try {
        const ev = JSON.parse(raw.data) as AgentEvent;
        const key = ev.id != null ? `e${ev.id}` : `${ev.run_id}:${ev.kind}:${ev.ts}`;
        if (seen.current.has(key)) return;
        seen.current.add(key);
        setEvents((prev) => [...prev.slice(-199), ev]);
      } catch {
        /* ignore malformed frames */
      }
    };

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = push;
    es.addEventListener("history", push as EventListener);
    return () => es.close();
  }, [profileId, enabled]);

  return { events, connected };
}
