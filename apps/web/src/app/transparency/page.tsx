"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Link2, ShieldCheck, ShieldAlert } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

interface Entry {
  id: number;
  certificate_code: string;
  digest: string;
  prev_hash: string;
  entry_hash: string;
  issued_at: string;
}

export default function Transparency() {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [chain, setChain] = useState<{ ok: boolean; entries: number } | null>(null);

  useEffect(() => {
    api<Entry[]>("/v1/transparency?limit=100", { auth: false }).then(setEntries).catch(() => setEntries([]));
    api<{ ok: boolean; entries: number }>("/v1/transparency/verify", { auth: false }).then(setChain).catch(() => {});
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="text-4xl font-semibold">Transparency log</h1>
      <p className="mt-2 max-w-2xl text-muted-foreground">
        Every certificate ever issued is appended here with the hash of the entry before it. Rewrite or delete history and every later
        entry stops matching. It stores only fingerprints — never personal data.
      </p>

      {chain && (
        <p className={`mt-6 inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium ${chain.ok ? "bg-verified-soft text-verified" : "bg-destructive/10 text-destructive"}`}>
          {chain.ok ? <ShieldCheck className="size-4" /> : <ShieldAlert className="size-4" />}
          {chain.ok ? `Chain intact — ${chain.entries} ${chain.entries === 1 ? "entry" : "entries"} verified end to end` : "Chain broken — history was altered"}
        </p>
      )}

      {!entries ? (
        <Skeleton className="mt-6 h-64 rounded-2xl" />
      ) : entries.length === 0 ? (
        <p className="mt-8 rounded-2xl border border-dashed border-border p-10 text-center text-muted-foreground">No certificates issued yet.</p>
      ) : (
        <ol className="mt-6 space-y-2">
          {entries.map((e) => (
            <li key={e.id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Link href={`/verify/${e.certificate_code}`} className="font-mono text-sm font-semibold text-primary hover:underline">
                  {e.certificate_code}
                </Link>
                <span className="text-xs text-muted-foreground">{e.issued_at}</span>
              </div>
              <dl className="mt-2 grid gap-0.5 font-mono text-[11px] text-muted-foreground">
                <div className="flex gap-2"><dt className="w-16 shrink-0">content</dt><dd className="break-all">{e.digest}</dd></div>
                <div className="flex gap-2"><dt className="w-16 shrink-0">previous</dt><dd className="break-all">{e.prev_hash}</dd></div>
                <div className="flex gap-2"><dt className="w-16 shrink-0 text-foreground"><Link2 className="mr-1 inline size-3" />entry</dt><dd className="break-all text-foreground">{e.entry_hash}</dd></div>
              </dl>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
