"use client";

import { SECTORS } from "@pramaan/ui/sectors";
import { ResultCard } from "@/components/directory/result-card";
import { SectorIcon } from "@/components/sector-icon";
import { SectorImage } from "@/components/sector-image";
import { Button } from "@/components/ui/button";
import type { Summary } from "@/lib/directory-types";

/**
 * One shelf of the registry (spec 6.2): a cover band for the field (an approved, attributed Unsplash photograph with the sector duotone, or the
 * sector-colour pattern until one exists), then one horizontal row of people that scrolls and snaps. The field is always named in words and
 * with its icon, never by colour alone.
 */
export function Shelf({ name, people, onSeeAll }: { name: string; people: Summary[]; onSeeAll: () => void }) {
  const meta = SECTORS.find((s) => s.name === name);
  const label = `${people.length} ${people.length === 1 ? "person" : "people"}`;
  return (
    <section aria-label={`${name}, ${label}`}>
      <div className="relative h-28 overflow-hidden rounded-[var(--radius-panel)] border border-border sm:h-32">
        <SectorImage sector={name} purpose="cover" width={1400} className="absolute inset-0 size-full rounded-none" />
        <div aria-hidden className="pointer-events-none absolute inset-0 bg-gradient-to-r from-[color-mix(in_srgb,var(--bond)_85%,transparent)] via-[color-mix(in_srgb,var(--bond)_30%,transparent)] to-transparent" />
        <div className="absolute inset-x-0 top-0 bottom-8 z-10 flex items-center justify-between gap-3 px-4">
          <h2 className="flex items-center gap-3 font-heading text-2xl font-semibold sm:text-3xl">
            <span className="inline-flex size-9 items-center justify-center rounded-full bg-background/90 shadow-sm">
              <SectorIcon name={meta?.icon ?? "landmark"} className="size-5" />
            </span>
            <span className="rounded-md bg-background/85 px-2 py-0.5">{name}</span>
          </h2>
          <Button variant="secondary" size="sm" className="bg-background/90" onClick={onSeeAll} aria-label={`See all ${label} in ${name}`}>
            See all {people.length}
          </Button>
        </div>
      </div>
      <ul className="-mx-4 mt-3 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-3 [scrollbar-width:thin]" tabIndex={0} aria-label={`${name} people, scroll sideways`}>
        {people.slice(0, 8).map((p, i) => (
          <ResultCard key={p.id} hit={p} index={i} className="w-[17rem] shrink-0 snap-start sm:w-[19rem] [&>a]:h-full" />
        ))}
      </ul>
    </section>
  );
}
