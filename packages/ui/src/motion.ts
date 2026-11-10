// Motion tokens (spec 4.6.2) as TypeScript constants, for the `motion` library. The CSS custom properties in tokens.css
// are the same numbers; keep them in sync (a test in apps/web checks that they are).

/** Durations in seconds (motion's unit). Exits take about 60% of the entrance. */
export const duration = { instant: 0.09, fast: 0.14, base: 0.22, slow: 0.36, hero: 0.64, epic: 1.2 } as const;

/** Cubic-bezier easings. */
export const ease = {
  standard: [0.2, 0, 0, 1],
  enter: [0.05, 0.7, 0.1, 1],
  exit: [0.3, 0, 0.8, 0.15],
  stamp: [0.34, 1.56, 0.64, 1], // slight overshoot: seals and stamps
  ink: [0.65, 0, 0.35, 1], // draw-on strokes
} as const;

/** Springs. */
export const spring = {
  snappy: { type: "spring", stiffness: 520, damping: 38, mass: 0.8 },
  soft: { type: "spring", stiffness: 260, damping: 28 },
  settle: { type: "spring", stiffness: 170, damping: 24 },
  stamp: { type: "spring", stiffness: 700, damping: 18, mass: 0.9 },
} as const;

/** Stagger between siblings, seconds. Cap staggered groups at 8 items; the rest appear instantly. */
export const STAGGER = 0.04;
export const MAX_STAGGERED = 8;

/** Delay for the i-th item of a staggered group (0 past the cap). */
export const staggerDelay = (i: number) => (i < MAX_STAGGERED ? i * STAGGER : 0);

/** Budget rules from the spec, enforced by code that uses these helpers. */
export const MAX_SIMULTANEOUS_ANIMATIONS = 6;
