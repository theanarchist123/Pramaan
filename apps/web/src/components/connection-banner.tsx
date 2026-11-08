"use client";

import { useCallback, useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { API_URL } from "@/lib/api";

type State = "ok" | "offline" | "server-down";

/** Tells people up front when they (or our server) are offline, instead of every page failing alone. */
export function ConnectionBanner() {
  const [state, setState] = useState<State>("ok");

  const check = useCallback(async () => {
    if (!navigator.onLine) return setState("offline");
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), 5000);
      const r = await fetch(`${API_URL}/healthz`, { signal: ctl.signal, cache: "no-store" });
      clearTimeout(t);
      setState(r.ok ? "ok" : "server-down");
    } catch {
      setState("server-down");
    }
  }, []);

  useEffect(() => {
    check();
    const on = () => check();
    window.addEventListener("online", on);
    window.addEventListener("offline", on);
    const id = setInterval(check, 20000);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", on);
      clearInterval(id);
    };
  }, [check]);

  if (state === "ok") return null;
  return (
    <div role="status" className="border-b border-pending/40 bg-pending-soft px-4 py-2 text-sm">
      <div className="mx-auto flex max-w-7xl items-center gap-3">
        <WifiOff className="size-4 shrink-0" aria-hidden="true" />
        <p className="flex-1">
          {state === "offline"
            ? "You're offline. Pages you've already opened still work; everything else needs a connection."
            : "We can't reach the Pramaan server right now. We'll keep trying — you don't need to refresh."}
        </p>
        <Button size="sm" variant="outline" onClick={check}>Retry now</Button>
      </div>
    </div>
  );
}
