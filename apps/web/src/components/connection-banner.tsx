"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { API_URL } from "@/lib/api";

type State = "ok" | "offline" | "waking" | "down";

/** Wait this long before saying anything: a free server that was asleep answers within a few seconds, and a banner that flashes up on every first visit looks broken. */
export const QUIET_MS = 4000;
/** After this long without an answer it is a real outage, not a wake-up. */
export const WAKING_MS = 60000;

/** What to show, from how long the server has been silent. Pure so it can be tested. */
export function stateFor(online: boolean, silentMs: number): State {
  if (!online) return "offline";
  if (silentMs < QUIET_MS) return "ok";
  return silentMs < WAKING_MS ? "waking" : "down";
}

/** Tells people when they (or our server) are offline, instead of every page failing alone. A floating pill below the navigation: it never covers the logo or the menu. */
export function ConnectionBanner() {
  const [state, setState] = useState<State>("ok");
  const silentSince = useRef<number | null>(null);

  const check = useCallback(async () => {
    if (!navigator.onLine) { silentSince.current = null; return setState("offline"); }
    const began = Date.now();
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), QUIET_MS); // no answer within the quiet period: count it as silence; the next try follows in 3 s
      const r = await fetch(`${API_URL}/healthz`, { signal: ctl.signal, cache: "no-store" });
      clearTimeout(t);
      if (!r.ok) throw new Error("not ok");
      silentSince.current = null;
      setState("ok");
    } catch {
      silentSince.current ??= began; // the silence began when we first asked, not when we gave up
      setState(stateFor(true, Date.now() - silentSince.current));
    }
  }, []);

  useEffect(() => {
    const on = () => void check();
    window.addEventListener("online", on);
    window.addEventListener("offline", on);
    // Ask, THEN decide how long to wait: quick while the server is silent (so the pill clears the moment it wakes), relaxed when all is well.
    let id: ReturnType<typeof setTimeout>;
    let stopped = false;
    const loop = async () => {
      await check();
      if (!stopped) id = setTimeout(loop, silentSince.current ? 3000 : 20000);
    };
    void loop();
    return () => {
      stopped = true;
      window.removeEventListener("online", on);
      window.removeEventListener("offline", on);
      clearTimeout(id);
    };
  }, [check]);

  if (state === "ok") return null;
  const waking = state === "waking";
  return (
    <div
      role="status"
      data-testid="connection-banner"
      className="pointer-events-none fixed inset-x-0 z-40 flex justify-center px-3 top-[calc(3.5rem+max(env(safe-area-inset-top),var(--safe-area-inset-top,0px))+0.5rem)] md:top-[4.75rem]"
    >
      <div className="pointer-events-auto flex max-w-xl items-center gap-3 rounded-full border border-pending/40 bg-pending-soft px-4 py-2 text-sm shadow-[var(--lift-1)]">
        {waking ? <Loader2 className="size-4 shrink-0 animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <WifiOff className="size-4 shrink-0" aria-hidden="true" />}
        <p className="min-w-0 flex-1">
          {state === "offline"
            ? "You're offline. Pages you've already opened still work; everything else needs a connection."
            : waking
              ? "Waking up the server. This takes a few seconds the first time."
              : "We can't reach the Pramaan server right now. We'll keep trying, you don't need to refresh."}
        </p>
        {state !== "waking" && <Button size="sm" variant="outline" onClick={() => void check()}>Retry now</Button>}
      </div>
    </div>
  );
}
