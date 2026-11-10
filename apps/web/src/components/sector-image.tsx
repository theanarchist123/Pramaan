"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { sectorByName } from "@pramaan/ui/sectors";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Approved {
  id: string;
  url_raw: string;
  dominant_color: string;
  alt: string;
  attribution: { photographer: string; photographer_url: string; photo_url: string; unsplash_url: string };
}

/**
 * A sector photograph from the approved set (spec 4.9, IMG-03).
 *  - HOTLINKED from Unsplash, sized with its image-CDN parameters; never downloaded or re-hosted. The `ixid` in the URL
 *    is kept (view tracking).
 *  - Duotone: the sector colour over a greyscale image, so mixed photographs read as one family.
 *  - ATTRIBUTION is always visible: "Photo by <name> on Unsplash", both linked with UTM parameters.
 *  - Never a broken image: while loading, if there are no approved images yet, or if the image fails, it shows the
 *    sector-tinted pattern instead.
 * Not for certificates (they use the frozen local photos) and never for people.
 */
export function SectorImage({
  sector,
  purpose = "tile",
  width = 640,
  className,
  index = 0,
}: {
  sector: string;
  purpose?: "tile" | "cover" | "empty";
  width?: number;
  className?: string;
  /** Which of the approved images to show (e.g. to vary neighbouring tiles). */
  index?: number;
}) {
  const { resolvedTheme } = useTheme();
  const [images, setImages] = useState<Approved[] | null>(null);
  const [failed, setFailed] = useState(false);
  const meta = sectorByName(sector);
  const tint = (resolvedTheme === "dark" ? meta?.dark : meta?.light) ?? "#4A2C8F";

  useEffect(() => {
    let live = true;
    api<Approved[]>(`/v1/images/sector/${encodeURIComponent(sector)}?purpose=${purpose}`, { auth: false })
      .then((r) => live && setImages(r))
      .catch(() => live && setImages([]));
    return () => {
      live = false;
    };
  }, [sector, purpose]);

  const img = images && images.length > 0 ? images[index % images.length] : null;
  const src = img ? `${img.url_raw}${img.url_raw.includes("?") ? "&" : "?"}w=${width}&q=70&fm=webp&fit=crop&auto=format` : "";

  return (
    <figure
      className={cn("relative isolate overflow-hidden rounded-[var(--radius-panel,12px)]", className)}
      style={{ ["--sector" as string]: tint, backgroundColor: `color-mix(in srgb, ${tint} 22%, transparent)` }}
    >
      {img && !failed ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose (Unsplash API terms) */}
          <img
            src={src}
            alt={img.alt}
            loading="lazy"
            onError={() => setFailed(true)}
            className="size-full object-cover grayscale contrast-[1.05]"
            style={{ backgroundColor: img.dominant_color || undefined }}
          />
          <span aria-hidden className="absolute inset-0 mix-blend-color" style={{ background: tint, opacity: 0.85 }} />
          <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-2 py-1 text-[11px] text-white/90">
            Photo by{" "}
            <a href={img.attribution.photographer_url} target="_blank" rel="noopener noreferrer" className="underline">
              {img.attribution.photographer}
            </a>{" "}
            on{" "}
            <a href={img.attribution.unsplash_url} target="_blank" rel="noopener noreferrer" className="underline">
              Unsplash
            </a>
          </figcaption>
        </>
      ) : (
        // Fallback: a sector-tinted pattern (no photo, so no attribution needed).
        <div
          aria-hidden
          className="size-full"
          style={{
            backgroundImage: `repeating-conic-gradient(from 0deg at 50% 120%, color-mix(in srgb, ${tint} 30%, transparent) 0 6deg, transparent 6deg 12deg)`,
          }}
        />
      )}
    </figure>
  );
}
