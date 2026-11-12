"use client";

import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { CONFIRMED } from "@/lib/claim-summary";
import type { Claim } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Split a biography into sentences without losing any character (so joining the parts gives the original text back). */
export function sentences(text: string): string[] {
  return text.match(/[^.!?।]+[.!?।]*\s*/g) ?? [text];
}

/**
 * "Show what's proven" (spec 6.3). Turning it on marks every sentence of the biography that contains, word for word, the text of a claim
 * the registry has CONFIRMED (a document, an issuer or a reviewer; a public-source quote or a self-claim does not count). It is a literal
 * text match against the server's own status, never a guess, and the legend says exactly that. Sentences that match nothing are left
 * plain, which is not a judgement that they are false: they simply have no confirmed claim behind them here.
 */
export function BioProof({ bio, claims }: { bio: string; claims: Claim[] }) {
  const [on, setOn] = useState(false);
  const confirmed = claims.filter((c) => CONFIRMED.includes(c.status) && c.value.trim().length >= 6).map((c) => c.value.trim().toLowerCase());
  const parts = sentences(bio);
  const matches = (s: string) => confirmed.some((v) => s.toLowerCase().includes(v));
  const count = parts.filter(matches).length;
  return (
    <div className="mt-5">
      <p className="max-w-2xl text-base leading-relaxed">
        {parts.map((s, i) => (
          <span key={i} className={cn(on && matches(s) && "rounded-sm bg-verified-soft px-0.5 text-verified underline decoration-verified/40 underline-offset-4")}>
            {s}
          </span>
        ))}
      </p>
      {confirmed.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            aria-pressed={on}
            onClick={() => setOn((v) => !v)}
            className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm", on ? "border-verified bg-verified-soft text-verified" : "border-border text-muted-foreground hover:text-foreground")}
          >
            <ShieldCheck aria-hidden className="size-4" /> Show what&apos;s proven
          </button>
          {on && (
            <p role="status" className="text-xs text-muted-foreground">
              {count === 0
                ? "No sentence repeats a confirmed claim word for word."
                : `${count} ${count === 1 ? "sentence repeats" : "sentences repeat"} a confirmed claim word for word. Unmarked sentences have no confirmed claim behind them here.`}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
