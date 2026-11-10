import { BadgeCheck, FileCheck2, Globe, MessageCircle, ShieldCheck, Stamp } from "lucide-react";
import type { ClaimStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const META: Record<ClaimStatus, { label: string; icon: typeof Globe; cls: string; hint: string }> = {
  self: {
    label: "Self-claimed",
    icon: MessageCircle,
    cls: "bg-pending-soft text-foreground/80 ring-pending/40",
    hint: "Said by the person; not backed by evidence yet",
  },
  web: {
    label: "Public evidence",
    icon: Globe,
    cls: "bg-indigo-soft text-indigo ring-indigo/30",
    hint: "Supported by a public source quoted verbatim",
  },
  document: {
    label: "Document verified",
    icon: FileCheck2,
    cls: "bg-verified-soft text-verified ring-verified/30",
    hint: "Backed by an uploaded credential whose holder matches",
  },
  human: {
    label: "Confirmed by a reviewer",
    icon: Stamp,
    cls: "bg-verified-soft text-verified ring-verified/30",
    hint: "A named reviewer confirmed it, with a written reason and evidence",
  },
  issuer: {
    label: "Verified by issuer",
    icon: ShieldCheck,
    cls: "bg-verified-soft text-verified ring-verified/30",
    hint: "Confirmed directly with the body that issued it",
  },
};

export function VerificationBadge({ status, className }: { status: ClaimStatus; className?: string }) {
  const m = META[status];
  const Icon = m.icon;
  return (
    <span
      title={m.hint}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        m.cls,
        className,
      )}
    >
      <Icon className="size-3" aria-hidden="true" /> {m.label}
    </span>
  );
}

export function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone = value >= 0.9 ? "bg-verified" : value >= 0.5 ? "bg-indigo" : "bg-pending";
  return (
    <div className="flex items-center gap-2" aria-label={`Confidence ${pct}%`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full transition-all duration-700", tone)} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-[11px] tabular-nums text-muted-foreground">{pct}%</span>
    </div>
  );
}

export function VerifiedSeal({ className }: { className?: string }) {
  return <BadgeCheck className={cn("size-5 text-verified", className)} aria-label="Verified" />;
}
