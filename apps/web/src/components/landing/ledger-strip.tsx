"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";

interface Entry { id: number; certificate_code: string; entry_hash: string; issued_at: string }

/** The newest entries of the public log, as they really are. Renders nothing while loading or when the log is empty. */
export function LedgerStrip() {
  const [entries, setEntries] = useState<Entry[]>([]);
  useEffect(() => {
    api<Entry[]>("/v1/transparency?limit=6", { auth: false }).then(setEntries).catch(() => {});
  }, []);
  if (entries.length === 0) return null;
  return (
    <section aria-label="Latest entries in the public log" className="mx-auto max-w-7xl px-4 pb-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-xl font-semibold">Latest in the public log</h2>
        <Link href="/transparency" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
          Check the whole chain <ArrowRight aria-hidden className="size-3.5" />
        </Link>
      </div>
      <ol className="mt-3 flex gap-2 overflow-x-auto pb-2">
        {entries.map((e) => (
          <li key={e.id} className="min-w-52 shrink-0 rounded-xl border border-border bg-card p-3">
            <Link href={`/verify/${e.certificate_code}`} className="font-mono text-sm font-semibold text-primary hover:underline">
              {e.certificate_code}
            </Link>
            <p className="mt-1 font-mono text-xs text-muted-foreground">{e.entry_hash.slice(0, 20)}...</p>
            <p className="text-xs text-muted-foreground">{e.issued_at}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
