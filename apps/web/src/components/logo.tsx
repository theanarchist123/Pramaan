import { cn } from "@/lib/utils";

/** Pramaan seal: a rangoli-like 8-petal rosette around a check — "proof". */
export function LogoMark({ className }: { className?: string }) {
  const petals = Array.from({ length: 8 }, (_, i) => i * 45);
  return (
    <svg viewBox="0 0 40 40" className={cn("size-8", className)} aria-hidden="true">
      <g transform="translate(20 20)">
        {petals.map((deg) => (
          <ellipse
            key={deg}
            rx="4.2"
            ry="9"
            transform={`rotate(${deg}) translate(0 -9)`}
            className="fill-primary/80"
          />
        ))}
        <circle r="8.5" className="fill-background" />
        <circle r="8.5" className="fill-none stroke-indigo" strokeWidth="1.4" />
        <path d="M-3.8 0.3 L-1 3.2 L4.2 -2.8" className="fill-none stroke-indigo" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="font-display text-xl font-semibold tracking-tight">Pramaan</span>
    </span>
  );
}
