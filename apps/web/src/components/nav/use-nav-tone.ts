"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

/**
 * The floating navigation has no background, so each piece must read as well over whatever is beneath it.
 * A page section declares what it is: data-nav-tone="on-light" (ink text) or "on-dark" (white text).
 * Anything undeclared is "auto": the theme's own foreground colour.
 */
export type NavTone = "auto" | "on-light" | "on-dark" | "inverse";
export type NavSpot = "logo" | "actions" | "dock";

const POINTS: Record<NavSpot, (w: number, h: number) => [number, number]> = {
  logo: () => [72, 40],
  actions: (w) => [Math.max(w - 120, 0), 40],
  dock: (w) => [w / 2, 92],
};

function toneAt(x: number, y: number): NavTone {
  for (const el of document.elementsFromPoint(x, y)) {
    if (el.closest("[data-floating-nav]")) continue;
    const hit = el.closest<HTMLElement>("[data-nav-tone]");
    if (hit) return (hit.dataset.navTone as NavTone) || "auto";
  }
  return "auto";
}

export function useNavTone(): Record<NavSpot, NavTone> {
  const pathname = usePathname();
  const [tones, setTones] = useState<Record<NavSpot, NavTone>>({ logo: "auto", actions: "auto", dock: "auto" });

  useEffect(() => {
    let frame = 0;
    const read = () => {
      frame = 0;
      const w = window.innerWidth;
      const h = window.innerHeight;
      const next = {} as Record<NavSpot, NavTone>;
      (Object.keys(POINTS) as NavSpot[]).forEach((k) => {
        const [x, y] = POINTS[k](w, h);
        next[k] = toneAt(x, y);
      });
      setTones((prev) => (prev.logo === next.logo && prev.actions === next.actions && prev.dock === next.dock ? prev : next));
    };
    const queue = () => {
      if (!frame) frame = requestAnimationFrame(read);
    };
    queue();
    const settle = window.setTimeout(queue, 400); // after the new page has painted
    window.addEventListener("scroll", queue, { passive: true });
    window.addEventListener("resize", queue);
    // A page can swap its own sections without a navigation (e.g. the onboarding start screen becoming the chat): re-read when the DOM changes.
    const watcher = new MutationObserver(queue);
    watcher.observe(document.body, { childList: true, subtree: true });
    return () => {
      watcher.disconnect();
      window.clearTimeout(settle);
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener("scroll", queue);
      window.removeEventListener("resize", queue);
    };
  }, [pathname]);

  return tones;
}

export const toneClass = (t: NavTone) =>
  t === "on-light" ? "text-[var(--on-brand)]" : t === "on-dark" ? "text-white" : t === "inverse" ? "text-background" : "text-foreground";
