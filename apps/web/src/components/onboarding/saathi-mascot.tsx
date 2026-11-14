"use client";

import { motion } from "motion/react";
import { useMotionPreference } from "@/lib/motion-preference";

export type SaathiState = "idle" | "listening" | "thinking" | "delighted";

const LABEL: Record<SaathiState, string> = {
  idle: "Saathi is ready",
  listening: "Saathi is listening",
  thinking: "Saathi is thinking",
  delighted: "Saathi is happy",
};

const INK = "#14152B";

/**
 * Saathi ("companion"): a marigold flower with a face. Petals turn slowly, the eyes blink, and the mood follows real events only:
 * `listening` while the microphone is on, `thinking` while a reply is pending, `delighted` when the server recorded something new.
 * Pure SVG + Motion (no asset to load). With reduced motion it is a still picture in the same mood.
 */
export function SaathiMascot({ state = "idle", size = 96, still = false, className = "" }: { state?: SaathiState; size?: number; still?: boolean; className?: string }) {
  const { reduced } = useMotionPreference();
  const move = !reduced && !still;
  const petals = Array.from({ length: 12 }, (_, i) => i * 30);

  const eyeY = state === "thinking" ? 53 : 56;
  const eyeDx = state === "thinking" ? 2 : 0;
  const eyeR = state === "listening" ? 4.6 : 3.4;

  return (
    <svg viewBox="0 0 120 120" width={size} height={size} role="img" aria-label={LABEL[state]} className={className}>
      {/* listening: sound rings */}
      {move && state === "listening" &&
        [0, 0.6].map((d) => (
          <motion.circle key={d} cx="60" cy="60" r="44" fill="none" stroke="#FFB81C" strokeWidth="2.5" initial={{ opacity: 0.6, scale: 0.8 }} animate={{ opacity: 0, scale: 1.35 }} transition={{ duration: 1.4, repeat: Infinity, delay: d, ease: "easeOut" }} style={{ originX: 0.5, originY: 0.5 }} />
        ))}

      <motion.g
        animate={move ? (state === "delighted" ? { scale: [1, 1.12, 1], rotate: [0, 8, -8, 0] } : { scale: 1 }) : undefined}
        transition={{ duration: 0.7, ease: "easeOut" }}
        style={{ originX: 0.5, originY: 0.5 }}
        key={state === "delighted" ? "joy" : "calm"}
      >
        {/* petals */}
        <motion.g animate={move ? { rotate: 360 } : undefined} transition={{ duration: state === "delighted" ? 8 : 48, repeat: Infinity, ease: "linear" }} style={{ originX: 0.5, originY: 0.5 }}>
          {petals.map((d) => (
            <ellipse key={d} cx="60" cy="21" rx="9.5" ry="17" transform={`rotate(${d} 60 60)`} fill={d % 60 === 0 ? "#FFB81C" : "#FFC94D"} stroke={INK} strokeWidth="2" />
          ))}
        </motion.g>

        {/* face */}
        <circle cx="60" cy="60" r="33" fill="#FFF1C2" stroke={INK} strokeWidth="2.5" />
        <circle cx="42" cy="66" r="5.5" fill="#FF9C86" opacity="0.65" />
        <circle cx="78" cy="66" r="5.5" fill="#FF9C86" opacity="0.65" />

        {/* eyes */}
        {state === "delighted" ? (
          <>
            <path d="M43 58 q6 -8 12 0" fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round" />
            <path d="M65 58 q6 -8 12 0" fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round" />
          </>
        ) : (
          [49, 71].map((cx) => (
            <motion.ellipse
              key={cx}
              cx={cx + eyeDx}
              cy={eyeY}
              rx={eyeR}
              ry={eyeR + 1.2}
              fill={INK}
              animate={move ? { scaleY: [1, 1, 0.1, 1] } : undefined}
              transition={{ duration: 4.2, repeat: Infinity, times: [0, 0.92, 0.96, 1] }}
              style={{ originX: 0.5, originY: 0.5 }}
            />
          ))
        )}

        {/* mouth */}
        {state === "delighted" ? (
          <path d="M46 66 q14 18 28 0 z" fill={INK} stroke={INK} strokeWidth="2" strokeLinejoin="round" />
        ) : state === "listening" ? (
          <ellipse cx="60" cy="72" rx="5" ry="6" fill={INK} />
        ) : state === "thinking" ? (
          <path d="M52 72 h13" stroke={INK} strokeWidth="3" strokeLinecap="round" fill="none" />
        ) : (
          <path d="M50 68 q10 9 20 0" fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round" />
        )}
      </motion.g>

      {/* thinking dots */}
      {state === "thinking" &&
        [0, 1, 2].map((i) => (
          <motion.circle key={i} cx={92 + i * 7} cy={26 - i * 3} r="2.6" fill={INK} animate={move ? { opacity: [0.2, 1, 0.2] } : undefined} transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }} />
        ))}

      {/* delighted sparkles */}
      {state === "delighted" &&
        [[16, 24], [104, 30], [100, 96]].map(([x, y], i) => (
          <motion.path key={i} d={`M${x} ${y - 7} l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2 z`} fill="#FFB81C" stroke={INK} strokeWidth="1.2" initial={{ scale: 0 }} animate={move ? { scale: [0, 1.2, 1] } : { scale: 1 }} transition={{ delay: 0.1 * i, duration: 0.5 }} style={{ originX: 0.5, originY: 0.5 }} />
        ))}
    </svg>
  );
}
