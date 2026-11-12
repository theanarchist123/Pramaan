"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, CheckCircle2, Link2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { verifyChainInBrowser, type ChainResult, type LogEntry } from "@/lib/chain-verify";
import { cn } from "@/lib/utils";

/**
 * The public log as a tape of linked entries. The chain is re-computed in this browser (SHA-256), not taken on the server's word, and
 * "Alter an entry" edits one in memory only, to show that changing any past entry breaks every link after it.
 */
export default function Transparency() {
  const [entries, setEntries] = useState<LogEntry[] | null>(null); // oldest first
  const [tampered, setTampered] = useState<number | null>(null);
  const [result, setResult] = useState<ChainResult | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    api<LogEntry[]>("/v1/transparency?limit=500", { auth: false })
      .then((l) => setEntries([...l].reverse()))
      .catch(() => setEntries([]));
  }, []);

  const shown = entries && tampered !== null ? entries.map((e, i) => (i === tampered ? { ...e, digest: e.digest.replace(/.$/, e.digest.endsWith("0") ? "1" : "0") } : e)) : entries;

  const check = useCallback(async () => {
    if (!shown) return;
    setChecking(true);
    setResult(await verifyChainInBrowser(shown));
    setChecking(false);
  }, [shown]);

  // Re-check whenever the entries (or the in-memory alteration) change.
  useEffect(() => {
    if (shown && shown.length) void check();
    else setResult(null);
  }, [shown, check]);

  const bad = result?.badIndex ?? null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="font-heading text-4xl font-semibold">Transparency log</h1>
      <p className="mt-2 max-w-2xl text-muted-foreground">
        Every certificate ever issued is appended here with the hash of the entry before it. Rewrite or delete history and every later entry
        stops matching. It stores only fingerprints, never personal data.
      </p>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        {shown && shown.length > 0 && (
          <p
            role="status"
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium",
              !result ? "bg-muted text-muted-foreground" : result.ok ? "bg-verified-soft text-verified" : "bg-destructive/10 text-destructive",
            )}
          >
            {checking || !result ? <Loader2 aria-hidden className="size-4 motion-safe:animate-spin" /> : result.ok ? <CheckCircle2 aria-hidden className="size-4" /> : <AlertCircle aria-hidden className="size-4" />}
            {!result
              ? "Checking the chain on this device"
              : result.ok
                ? `Chain intact: ${shown.length} ${shown.length === 1 ? "entry" : "entries"} re-computed on this device${result.fromStart ? ", from the first entry" : ""}`
                : result.why === "link"
                  ? `Chain broken at entry ${bad! + 1}: it does not point at the entry before it`
                  : `Chain broken at entry ${bad! + 1}: its content no longer matches its hash`}
          </p>
        )}
        {shown && shown.length > 1 && (
          <Button variant="outline" size="sm" onClick={() => setTampered(tampered === null ? Math.max(0, Math.floor(shown.length / 2) - 1) : null)}>
            {tampered === null ? "Alter an entry (demo)" : "Undo the alteration"}
          </Button>
        )}
      </div>
      {tampered !== null && (
        <p className="mt-2 text-sm text-muted-foreground">One fingerprint was changed in your browser only. Nothing was sent to the registry.</p>
      )}

      {!shown ? (
        <Skeleton className="mt-6 h-64 rounded-2xl" />
      ) : shown.length === 0 ? (
        <p className="mt-8 rounded-2xl border border-dashed border-border p-10 text-center text-muted-foreground">No certificates issued yet.</p>
      ) : (
        <ol className="mt-6 space-y-2" aria-label="Log entries, newest first">
          {[...shown].reverse().map((e, r) => {
            const i = shown.length - 1 - r;
            const broken = bad !== null && i >= bad;
            return (
              <li key={e.id} className={cn("rounded-xl border bg-card p-4", broken ? "border-destructive/60" : "border-border")}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Link href={`/verify/${e.certificate_code}`} className="font-mono text-sm font-semibold text-primary hover:underline">
                    {e.certificate_code}
                  </Link>
                  <span className="flex items-center gap-3 text-xs text-muted-foreground">
                    {broken && <span className="inline-flex items-center gap-1 text-destructive"><AlertCircle aria-hidden className="size-3.5" /> {i === bad ? "First mismatch" : "Follows a mismatch"}</span>}
                    {e.issued_at}
                  </span>
                </div>
                <dl className="mt-2 grid gap-0.5 font-mono text-xs text-muted-foreground">
                  <div className="flex gap-2"><dt className="w-16 shrink-0">content</dt><dd className="break-all">{e.digest}</dd></div>
                  <div className="flex gap-2"><dt className="w-16 shrink-0">previous</dt><dd className="break-all">{e.prev_hash}</dd></div>
                  <div className="flex gap-2"><dt className="w-16 shrink-0 text-foreground"><Link2 aria-hidden className="mr-1 inline size-3" />entry</dt><dd className="break-all text-foreground">{e.entry_hash}</dd></div>
                </dl>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
