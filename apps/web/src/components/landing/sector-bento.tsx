"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SECTORS } from "@pramaan/ui/sectors";
import { SectorIcon } from "@/components/sector-icon";
import { SectorImage } from "@/components/sector-image";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Browse by field (spec 6.1): a bento of sector tiles. The two sectors with the most verified people are large. Each tile has the
 * sector's icon, name and count, and a hotlinked Unsplash photograph (duotone, attributed) when one has been approved for that sector;
 * otherwise the sector-tinted pattern. The link covers the tile except the strip where the photo credit sits, so the credit stays clickable.
 */
export function SectorBento() {
  const [counts, setCounts] = useState<Record<string, number> | null>(null);
  useEffect(() => {
    api<{ by_sector: Record<string, number> }>("/v1/stats/map", { auth: false }).then((s) => setCounts(s.by_sector)).catch(() => setCounts({}));
  }, []);

  const ranked = [...SECTORS].sort((a, b) => (counts?.[b.name] ?? 0) - (counts?.[a.name] ?? 0));
  return (
    <ul className="grid auto-rows-[9rem] grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
      {ranked.map((s, i) => {
        const big = i < 2 && (counts?.[s.name] ?? 0) > 0;
        const n = counts?.[s.name] ?? 0;
        return (
          <li key={s.slug} className={cn("relative min-h-0 overflow-hidden rounded-[var(--radius-panel)] border border-border shadow-[var(--lift-1)]", big && "col-span-2 row-span-2 lg:col-span-3")}>
            <SectorImage sector={s.name} purpose="tile" index={i} width={big ? 960 : 480} className="absolute inset-0 size-full rounded-none" />
            <div aria-hidden className="pointer-events-none absolute inset-0 bg-gradient-to-b from-[color-mix(in_srgb,var(--bond)_78%,transparent)] via-transparent to-transparent" />
            <Link
              href={`/directory?sector=${encodeURIComponent(s.name)}`}
              aria-label={`${s.name}: ${n} ${n === 1 ? "person" : "people"}`}
              className="absolute inset-x-0 top-0 bottom-8 z-10 flex flex-col justify-between p-3 focus-visible:outline-2 focus-visible:outline-offset-[-3px] focus-visible:outline-ring"
            >
              <span className="inline-flex size-8 items-center justify-center rounded-full bg-background/85 text-foreground shadow-sm">
                <SectorIcon name={s.icon} className="size-4" />
              </span>
              <span className="w-fit rounded-md bg-background/85 px-2 py-1 text-foreground shadow-sm">
                <span className={cn("block font-heading font-semibold leading-tight", big ? "text-xl" : "text-sm")}>{s.name}</span>
                <span className="block text-xs text-muted-foreground tabular-nums">{n} {n === 1 ? "person" : "people"}</span>
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
