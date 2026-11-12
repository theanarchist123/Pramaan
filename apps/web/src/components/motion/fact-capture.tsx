"use client";

import { motion } from "motion/react";
import { useMotionPreference } from "@/lib/motion-preference";

/**
 * M-03 fact capture: when a fact the person just said lands on their profile, the row slides in 16 px and a wash of the
 * primary colour fades out behind it, so the eye can follow where the words went. Transform and opacity only for the move;
 * the wash is an overlay whose opacity changes. Reduced motion: the row is simply there, no wash.
 */
export function FactCapture({ children, className }: { children: React.ReactNode; className?: string }) {
  const { reduced } = useMotionPreference();
  if (reduced) return <li className={className}>{children}</li>;
  return (
    <motion.li layout initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.32, ease: [0.2, 0.8, 0.2, 1] }} className={`relative ${className ?? ""}`}>
      <motion.span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[inherit] bg-primary/15"
        initial={{ opacity: 1 }}
        animate={{ opacity: 0 }}
        transition={{ duration: 0.9, delay: 0.2 }}
      />
      {children}
    </motion.li>
  );
}
