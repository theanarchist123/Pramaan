"use client";

import { motion } from "motion/react";
import { spring } from "@pramaan/ui/motion";
import { useMotionPreference } from "@/lib/motion-preference";

/**
 * M-01 seal landing (small): the mark scales 1.35 -> 1 with a stamp spring and a one-shot ring blooms from it. Use it only when
 * a real check has just passed. Reduced motion: the mark is simply there.
 */
export function SealLanding({ children, ring = true }: { children: React.ReactNode; ring?: boolean }) {
  const { reduced } = useMotionPreference();
  if (reduced) return <span className="relative inline-flex">{children}</span>;
  return (
    <span className="relative inline-flex">
      {ring && (
        <motion.span
          aria-hidden
          className="absolute inset-0 rounded-full border-2 border-current opacity-0"
          initial={{ scale: 0.6, opacity: 0.35 }}
          animate={{ scale: 1.5, opacity: 0 }}
          transition={{ duration: 0.52, delay: 0.16, ease: "easeOut" }}
        />
      )}
      <motion.span initial={{ scale: 1.35, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ ...spring.stamp, opacity: { duration: 0.1 } }}>
        {children}
      </motion.span>
    </span>
  );
}
