// Generative certificate art. Everything is a pure function of the certificate's SHA-256 digest,
// so the artwork is the fingerprint: different content → different art, same content → identical art.

export interface Palette {
  ink: string;
  primary: string;
  secondary: string;
}

export const SECTOR_PALETTE: Record<string, Palette> = {
  Science: { ink: "#1d4e89", primary: "#2a9d8f", secondary: "#e9c46a" },
  Technology: { ink: "#264653", primary: "#2a9d8f", secondary: "#e76f51" },
  Healthcare: { ink: "#1b6b5a", primary: "#4cb5a0", secondary: "#e5989b" },
  Education: { ink: "#5a3e8a", primary: "#8e6bbf", secondary: "#e9b44c" },
  "Arts & Culture": { ink: "#8c2f39", primary: "#e07a5f", secondary: "#f2cc8f" },
  Literature: { ink: "#5c3a21", primary: "#a5673f", secondary: "#d4a373" },
  Sports: { ink: "#b23a1f", primary: "#f4a259", secondary: "#2b6777" },
  Business: { ink: "#1b2a49", primary: "#3d5a80", secondary: "#c8963e" },
  "Public Service": { ink: "#1f4287", primary: "#e8871e", secondary: "#138808" },
  Law: { ink: "#3b2a20", primary: "#7a5c3e", secondary: "#b08d57" },
  Media: { ink: "#2b2d42", primary: "#8d99ae", secondary: "#ef233c" },
  "Social Work": { ink: "#9d2a4e", primary: "#e76f51", secondary: "#f4a261" },
  Agriculture: { ink: "#386641", primary: "#6a994e", secondary: "#bc4749" },
  Energy: { ink: "#b5651d", primary: "#f2a900", secondary: "#2a6f97" },
  Other: { ink: "#3d405b", primary: "#81b29a", secondary: "#e07a5f" },
};

export function paletteFor(sector?: string | null): Palette {
  return SECTOR_PALETTE[sector ?? ""] ?? SECTOR_PALETTE.Other;
}

/** sfc32 PRNG seeded from the first 128 bits of a hex digest. */
export function rngFromHex(hex: string): () => number {
  const word = (i: number) => parseInt(hex.slice(i * 8, i * 8 + 8).padEnd(8, "0"), 16) >>> 0;
  let a = word(0), b = word(1), c = word(2), d = word(3);
  return () => {
    a >>>= 0; b >>>= 0; c >>>= 0; d >>>= 0;
    let t = (a + b) | 0;
    a = b ^ (b >>> 9);
    b = (c + (c << 3)) | 0;
    c = (c << 21) | (c >>> 11);
    d = (d + 1) | 0;
    t = (t + d) | 0;
    c = (c + t) | 0;
    return (t >>> 0) / 4294967296;
  };
}

const f = (n: number) => (Math.round(n * 10) / 10).toString();
const gcd = (a: number, b: number): number => (b === 0 ? a : gcd(b, a % b));

export interface RosetteLayer {
  petals: number;
  inner: number;
  outer: number;
  width: number;
  rotation: number;
  color: "ink" | "primary" | "secondary";
  filled: boolean;
  opacity: number;
}

export interface Rosette {
  layers: RosetteLayer[];
  dotRings: { radius: number; count: number; size: number; color: "ink" | "primary" | "secondary" }[];
  starPoints: number;
}

/** A rangoli-style rosette: concentric petal rings + dotted rings, all from the seed. */
export function makeRosette(seed: string, salt = 0): Rosette {
  const rnd = rngFromHex(seed.slice(salt * 4) + seed);
  const pick = <T,>(arr: T[]) => arr[Math.floor(rnd() * arr.length)];
  const layerCount = 5 + Math.floor(rnd() * 3);
  const colors: ("ink" | "primary" | "secondary")[] = ["ink", "primary", "secondary"];
  const layers: RosetteLayer[] = [];
  for (let i = 0; i < layerCount; i++) {
    const outer = ((i + 1.4) / (layerCount + 0.4)) * 100;
    layers.push({
      petals: pick([8, 10, 12, 16, 20, 24]),
      inner: outer * (0.35 + rnd() * 0.25),
      outer,
      width: 0.22 + rnd() * 0.3,
      rotation: rnd() * 360,
      color: colors[i % 3 === 0 ? Math.floor(rnd() * 3) : (i + 1) % 3],
      filled: rnd() > 0.4,
      opacity: 0.75 + rnd() * 0.25,
    });
  }
  const dotRings = Array.from({ length: 2 + Math.floor(rnd() * 2) }, () => ({
    radius: 30 + rnd() * 65,
    count: pick([24, 32, 40, 48]),
    size: 0.7 + rnd() * 1.1,
    color: pick(colors),
  }));
  return { layers, dotRings, starPoints: pick([6, 8, 12]) };
}

/** SVG path for one petal along +x between radii r0 and r1. */
export function petalPath(r0: number, r1: number, width: number): string {
  const mid = (r0 + r1) / 2;
  const w = (r1 - r0) * width;
  return `M${f(r0)} 0 Q${f(mid)} ${f(w)} ${f(r1)} 0 Q${f(mid)} ${f(-w)} ${f(r0)} 0Z`;
}

/** Hypotrochoid (spirograph) path — the banknote "guilloche" look — seeded by the digest. */
export function guillochePath(seed: string, radius = 100): string {
  const rnd = rngFromHex(seed.slice(16) + seed);
  const R = 70 + Math.floor(rnd() * 40);
  const r = 9 + Math.floor(rnd() * 28);
  const d = r * (0.55 + rnd() * 0.8);
  const turns = r / gcd(R, r);
  const steps = Math.min(4200, Math.round(turns * 360));
  const k = (R - r) / r;
  const raw: [number, number][] = [];
  let max = 0;
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * Math.PI * 2 * turns;
    const x = (R - r) * Math.cos(t) + d * Math.cos(k * t);
    const y = (R - r) * Math.sin(t) - d * Math.sin(k * t);
    raw.push([x, y]);
    max = Math.max(max, Math.hypot(x, y));
  }
  const s = radius / max;
  return raw.map(([x, y], i) => `${i ? "L" : "M"}${f(x * s)} ${f(y * s)}`).join("");
}
