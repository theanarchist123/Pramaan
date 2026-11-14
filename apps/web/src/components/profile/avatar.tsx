import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

/** A coloured initials tile (no stock photos of people). A member-uploaded photo, once supported, replaces it. */
export function initialsOf(name: string): string {
  return name.replace(/^(dr|prof|shri|smt)\.?\s+/i, "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => Array.from(w)[0]).join("").toUpperCase();
}

export function tileOf(name: string): number {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.codePointAt(0)!) >>> 0;
  return (h % 6) + 1;
}

export function Avatar({ name, photo, verified, className }: { name: string; photo?: string; verified?: boolean; className?: string }) {
  const n = tileOf(name);
  return (
    <span
      aria-hidden
      className={cn("relative inline-flex size-14 shrink-0 items-center justify-center rounded-[1.1rem] font-display text-xl font-extrabold", className)}
      style={{ background: `var(--tile${n})`, color: `var(--tile${n}i)` }}
    >
      {photo ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={photo} alt="" className="size-full rounded-[inherit] object-cover" />
      ) : (
        initialsOf(name)
      )}
      {verified && (
        <span title="Approved by the registry" className="absolute -bottom-1.5 -right-1.5 inline-flex size-5 items-center justify-center rounded-full border-2 border-background bg-[var(--verified)] text-white">
          <Check className="size-3" strokeWidth={3.5} />
        </span>
      )}
    </span>
  );
}
