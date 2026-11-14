"use client";

import { useEffect, useRef } from "react";
import { annotate } from "rough-notation";
import { useMotionPreference } from "@/lib/motion-preference";

/** One hand-drawn emphasis per page (motion V-13). Skipped animation, not skipped meaning, when motion is reduced. */
export function HandUnderline({ children, color = "#14152B" }: { children: React.ReactNode; color?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const { reduced } = useMotionPreference();
  useEffect(() => {
    if (!ref.current) return;
    const a = annotate(ref.current, { type: "underline", color, strokeWidth: 4, padding: 2, animate: !reduced, animationDuration: 700 });
    const id = window.setTimeout(() => a.show(), 500);
    return () => {
      window.clearTimeout(id);
      a.remove();
    };
  }, [reduced, color]);
  return <span ref={ref}>{children}</span>;
}
