"use client";

import { useEffect, useMemo, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
import type { MapStats } from "@/lib/directory-types";
import { cn } from "@/lib/utils";

interface Feature {
  properties: { name: string };
  geometry: { type: "MultiPolygon"; coordinates: number[][][][] };
}

const W = 560;
const H = 640;

/**
 * Choropleth of registry members by state. Source boundaries predate 2019, so Ladakh shares the
 * Jammu & Kashmir shape: its members are counted there (shown in the tooltip).
 */
export function IndiaMap({
  stats, selected, onSelect,
}: {
  stats: MapStats | null;
  selected: string | null;
  onSelect: (state: string | null) => void;
}) {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [hover, setHover] = useState<{ name: string; x: number; y: number } | null>(null);

  useEffect(() => {
    fetch("/india-states.json").then((r) => r.json()).then((d) => setFeatures(d.features)).catch(() => {});
  }, []);

  const counts = useMemo(() => {
    const c: Record<string, number> = { ...(stats?.by_state ?? {}) };
    if (c["Ladakh"]) c["Jammu and Kashmir"] = (c["Jammu and Kashmir"] ?? 0) + c["Ladakh"];
    return c;
  }, [stats]);
  const max = Math.max(1, ...Object.values(counts));

  const paths = useMemo(() => {
    if (!features.length) return [];
    const projection = geoMercator().fitExtent(
      [[8, 8], [W - 8, H - 8]],
      { type: "FeatureCollection", features } as unknown as GeoJSON.FeatureCollection,
    );
    const path = geoPath(projection);
    return features.map((f) => ({ name: f.properties.name, d: path(f as unknown as GeoJSON.Feature) ?? "" }));
  }, [features]);

  return (
    <div className="relative mx-auto w-full max-w-xl">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Map of India showing registry members per state">
        {paths.map((p) => {
          const n = counts[p.name] ?? 0;
          const isSel = selected === p.name || (selected === "Ladakh" && p.name === "Jammu and Kashmir");
          return (
            <path
              key={p.name}
              d={p.d}
              tabIndex={0}
              role="button"
              aria-label={`${p.name}: ${n} member${n === 1 ? "" : "s"}`}
              onClick={() => onSelect(isSel ? null : p.name)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(isSel ? null : p.name)}
              onMouseMove={(e) => {
                const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
                setHover({ name: p.name, x: e.clientX - r.left, y: e.clientY - r.top });
              }}
              onMouseLeave={() => setHover(null)}
              className={cn("cursor-pointer outline-none transition-colors focus-visible:stroke-foreground", isSel ? "stroke-foreground" : "stroke-background")}
              strokeWidth={isSel ? 2 : 0.7}
              fill={n ? `color-mix(in oklch, var(--primary) ${Math.round(18 + (n / max) * 72)}%, var(--card))` : "var(--muted)"}
            />
          );
        })}
      </svg>
      {hover && (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-lg bg-foreground px-2.5 py-1.5 text-xs text-background shadow-lg"
          style={{ left: hover.x, top: hover.y - 10 }}
        >
          <p className="font-semibold">{hover.name}</p>
          <p>
            {counts[hover.name] ?? 0} member{(counts[hover.name] ?? 0) === 1 ? "" : "s"}
            {hover.name === "Jammu and Kashmir" && stats?.by_state?.Ladakh ? ` (incl. ${stats.by_state.Ladakh} in Ladakh)` : ""}
          </p>
        </div>
      )}
      <div className="mt-2 flex items-center justify-center gap-2 text-[11px] text-muted-foreground">
        <span>Fewer</span>
        <span className="h-2 w-28 rounded-full" style={{ background: "linear-gradient(90deg, color-mix(in oklch, var(--primary) 18%, var(--card)), var(--primary))" }} />
        <span>More members</span>
      </div>
    </div>
  );
}
