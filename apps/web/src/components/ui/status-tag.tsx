import { BadgeCheck, Globe, ShieldCheck, UserRound } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * A claim's status as icon + text + colour (never colour alone). The kind comes from the server's own status enum
 * (claim.status), so nothing here can say "verified" on its own (invariant I-9).
 */
export type StatusKind = "document" | "issuer" | "human" | "web" | "self";

const KINDS: Record<StatusKind, { label: string; Icon: typeof BadgeCheck; cls: string }> = {
  document: { label: "Document verified", Icon: BadgeCheck, cls: "bg-[var(--verified-tint)] text-[var(--verified)]" },
  issuer: { label: "Issuer verified", Icon: ShieldCheck, cls: "bg-[var(--verified-tint)] text-[var(--verified)]" },
  human: { label: "Reviewer confirmed", Icon: BadgeCheck, cls: "bg-[var(--verified-tint)] text-[var(--verified)]" },
  web: { label: "Public record", Icon: Globe, cls: "bg-[var(--public-tint)] text-[var(--public)]" },
  self: { label: "Self-declared", Icon: UserRound, cls: "bg-[var(--self-tint)] text-[var(--self)]" },
};

export function StatusTag({ kind, className }: { kind: StatusKind; className?: string }) {
  const { label, Icon, cls } = KINDS[kind] ?? KINDS.self;
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full py-0.5 pl-2 pr-2.5 text-xs font-semibold", cls, className)}>
      <Icon aria-hidden className="size-3.5" /> {label}
    </span>
  );
}
