"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { MotionConfig } from "motion/react";

const KEY = "pramaan.reduceMotion";

interface MotionPref {
  /** True when the person (or their OS) asked for less motion. Every animation must have a still variant for this. */
  reduced: boolean;
  setReduced: (v: boolean) => void;
}

const Ctx = createContext<MotionPref>({ reduced: false, setReduced: () => {} });

/**
 * Honours the OS "reduce motion" setting AND an in-app switch (spec MOT-01). The choice is remembered per viewer in
 * localStorage (a convenience only: the page works without it) and mirrored to <html data-reduce-motion> so plain CSS
 * animations stop too. `motion` components follow it through MotionConfig.
 */
export function MotionPreferenceProvider({ children }: { children: React.ReactNode }) {
  const [reduced, setState] = useState(false);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(KEY);
    } catch {
      /* storage blocked: fall back to the OS setting */
    }
    setState(stored !== null ? stored === "true" : window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.reduceMotion = String(reduced);
  }, [reduced]);

  const setReduced = useCallback((v: boolean) => {
    setState(v);
    try {
      localStorage.setItem(KEY, String(v));
    } catch {
      /* per-viewer convenience only */
    }
  }, []);

  return (
    <Ctx.Provider value={{ reduced, setReduced }}>
      <MotionConfig reducedMotion={reduced ? "always" : "user"}>{children}</MotionConfig>
    </Ctx.Provider>
  );
}

export function useMotionPreference(): MotionPref {
  return useContext(Ctx);
}
