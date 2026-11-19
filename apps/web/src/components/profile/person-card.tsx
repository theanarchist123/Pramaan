import Link from "next/link";
import { MapPin } from "lucide-react";
import { Avatar } from "@/components/profile/avatar";
import { cn } from "@/lib/utils";

export interface PersonSummary {
  slug: string;
  full_name: string;
  headline: string;
  sector: string;
  state: string;
  city: string;
  photo_url?: string;
  status?: string;
  is_demo?: boolean;
}

/** A person as a card: initials avatar (tick only when the server says approved), name, headline, field and place. */
export function PersonCard({ p, className }: { p: PersonSummary; className?: string }) {
  return (
    <Link
      href={`/p/${p.slug}`}
      className={cn(
        "group flex h-full min-w-0 flex-col gap-3 rounded-[1.4rem] border border-border bg-card p-4 shadow-[var(--lift-1)] transition-transform hover:-translate-y-1 focus-visible:outline-2 focus-visible:outline-offset-2",
        className,
      )}
    >
      <div className="flex items-center gap-3.5">
        <Avatar name={p.full_name} photo={p.photo_url} verified={p.status === "approved"} />
        <div className="min-w-0">
          <p className="truncate font-display text-lg font-bold leading-tight">{p.full_name}</p>
          <p className="mt-0.5 flex items-center gap-1 text-sm text-muted-foreground">
            <MapPin aria-hidden className="size-3.5 shrink-0" />
            <span className="truncate">{[p.city, p.state].filter(Boolean).join(", ") || "India"}</span>
          </p>
        </div>
      </div>
      <p className="line-clamp-2 text-sm font-medium">{p.headline || p.sector}</p>
      <span className="mt-auto flex flex-wrap gap-1.5">
        <span className="inline-flex w-fit rounded-full bg-muted px-2.5 py-0.5 text-xs font-semibold">{p.sector}</span>
        {p.is_demo && <span className="inline-flex w-fit rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">Fictional demo</span>}
      </span>
    </Link>
  );
}
