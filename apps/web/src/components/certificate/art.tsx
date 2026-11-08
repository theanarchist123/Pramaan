"use client";

import { useMemo } from "react";
import { guillochePath, makeRosette, paletteFor, petalPath } from "@/lib/certificate-art";

/** The rosette seal. `seed` is the certificate digest. */
export function Rosette({ seed, sector, size = 220, salt = 0 }: { seed: string; sector?: string | null; size?: number; salt?: number }) {
  const palette = paletteFor(sector);
  const rosette = useMemo(() => makeRosette(seed, salt), [seed, salt]);
  return (
    <svg viewBox="-110 -110 220 220" width={size} height={size} aria-hidden="true">
      {rosette.layers.map((l, i) => {
        const d = petalPath(l.inner, l.outer, l.width);
        const color = palette[l.color];
        return (
          <g key={i} transform={`rotate(${l.rotation.toFixed(1)})`} opacity={l.opacity}>
            {Array.from({ length: l.petals }, (_, p) => (
              <path
                key={p}
                d={d}
                transform={`rotate(${(360 / l.petals) * p})`}
                fill={l.filled ? color : "none"}
                fillOpacity={l.filled ? 0.5 : 0}
                stroke={color}
                strokeWidth={1.1}
              />
            ))}
          </g>
        );
      })}
      {rosette.dotRings.map((ring, i) =>
        Array.from({ length: ring.count }, (_, k) => {
          const a = (k / ring.count) * Math.PI * 2;
          return <circle key={`${i}-${k}`} cx={Math.cos(a) * ring.radius} cy={Math.sin(a) * ring.radius} r={ring.size} fill={palette[ring.color]} opacity={0.95} />;
        }),
      )}
      <g fill={palette.ink}>
        <circle r={5.5} />
        {Array.from({ length: rosette.starPoints }, (_, i) => (
          <path key={i} d="M0 -14 L2.2 -6 L-2.2 -6Z" transform={`rotate(${(360 / rosette.starPoints) * i})`} opacity={0.85} />
        ))}
      </g>
    </svg>
  );
}

/** Large, faint guilloche used as the certificate's background texture. */
export function Guilloche({ seed, sector, size = 520 }: { seed: string; sector?: string | null; size?: number }) {
  const palette = paletteFor(sector);
  const d = useMemo(() => guillochePath(seed, 100), [seed]);
  return (
    <svg viewBox="-100 -100 200 200" width={size} height={size} aria-hidden="true">
      <path d={d} fill="none" stroke={palette.primary} strokeWidth={0.18} opacity={0.7} />
      <path d={d} fill="none" stroke={palette.ink} strokeWidth={0.08} opacity={0.5} transform="rotate(7)" />
    </svg>
  );
}
