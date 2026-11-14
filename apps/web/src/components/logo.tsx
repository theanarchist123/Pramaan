import { cn } from "@/lib/utils";

/** Pramaan mark: a marigold tile with a check ("proven"). Works on the page and on the paper certificate. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("size-8", className)} aria-hidden="true">
      <rect width="40" height="40" rx="12" fill="#FFB81C" />
      <path d="M11 20.5l6.2 6.2L29.5 13.5" fill="none" stroke="#14152B" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="font-display text-2xl font-extrabold tracking-tight">Pramaan</span>
    </span>
  );
}
