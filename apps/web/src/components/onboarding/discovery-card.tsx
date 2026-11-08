"use client";

import { motion } from "motion/react";
import { Check, ExternalLink, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { DiscoveryResult } from "@/lib/types";

export function DiscoveryCard({
  result,
  busy,
  onConfirm,
  onReject,
}: {
  result: DiscoveryResult;
  busy: boolean;
  onConfirm: () => void;
  onReject: () => void;
}) {
  const d = result.draft!;
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-4 mt-3 rounded-2xl border border-indigo/30 bg-indigo-soft/60 p-4"
      role="region"
      aria-label="Is this you?"
    >
      <p className="flex items-center gap-2 text-xs font-medium text-indigo">
        <Search className="size-3.5" /> Khoji-Pehle found a public page — is this you?
      </p>
      <p className="mt-2 font-display text-lg font-semibold">{result.source_title}</p>
      {d.headline && <p className="text-sm text-muted-foreground line-clamp-2">{d.headline}</p>}
      {d.claims.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {d.claims.slice(0, 4).map((c, i) => (
            <li key={i} className="flex gap-2">
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-indigo" />
              <span className="line-clamp-2">{c.value}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-muted-foreground">
        Suggestions only — they stay <em>self-claimed</em> until Pariksha verifies them.{" "}
        <a href={result.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline">
          View source <ExternalLink className="size-3" />
        </a>
      </p>
      <div className="mt-3 flex gap-2">
        <Button onClick={onConfirm} disabled={busy}>
          <Check /> Yes, that&apos;s me
        </Button>
        <Button variant="ghost" onClick={onReject} disabled={busy}>
          <X /> Not me
        </Button>
      </div>
    </motion.div>
  );
}
