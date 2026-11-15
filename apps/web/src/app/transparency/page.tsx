"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, CheckCircle2, Link2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { verifyChainInBrowser, type ChainResult, type LogEntry } from "@/lib/chain-verify";
import { cn } from "@/lib/utils";

/**
 * The ledger tape (spec 6.6): every certificate ever issued, newest first, each entry chained to the one before it. Nothing is checked until
 * you press the button; then this browser re-computes every SHA-256 link itself (with a progress bar), so the answer does not rest on the
 * server's word. "Alter an entry" changes one fingerprint in memory only, to show that rewriting any past entry breaks every link after it.
 */
export default function Transparency() {
  const [entries, setEntries] = useState<LogEntry[] | null>(null); // oldest first
  const [tampered, setTampered] = useState<number | null>(null);
  const [result, setResult] = useState<ChainResult | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [everChecked, setEverChecked] = useState(false);
  const [visible, setVisible] = useState(25); // the tape shows the newest entries; the CHECK always covers the whole chain

  useEffect(() => {
    api<LogEntry[]>("/v1/transparency?limit=500", { auth: false })
      .then((l) => setEntries([...l].reverse()))
      .catch(() => setEntries([]));
  }, []);

  const shown = entries && tampered !== null ? entries.map((e, i) => (i === tampered ? { ...e, digest: e.digest.replace(/.$/, e.digest.endsWith("0") ? "1" : "0") } : e)) : entries;

  const check = useCallback(async (list: LogEntry[]) => {
    setEverChecked(true);
    setResult(null);
    setProgress({ done: 0, total: list.length });
    const r = await verifyChainInBrowser(list, (done, total) => setProgress({ done, total }));
    setProgress(null);
    setResult(r);
  }, []);

  // Once a person has run the check, an in-memory alteration (or undoing it) re-runs it so the effect is visible straight away.
  useEffect(() => {
    if (everChecked && shown && shown.length) void check(shown);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to the alteration, not to every render
  }, [tampered]);

  const bad = result?.badIndex ?? null;
  const running = progress !== null;
  // A broken link must never be hidden below the fold: show at least up to (and a little past) the first mismatch.
  const total = shown?.length ?? 0;
  const shownCount = Math.min(total, Math.max(visible, bad !== null ? total - bad + 2 : 0));

  return (
    <div className="md:-mt-16">
      <section data-nav-tone="on-dark" className="relative overflow-hidden bg-[#14152B] text-white">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 flex gap-2 overflow-hidden px-4 opacity-25">
          {Array.from({ length: 14 }, (_, i) => (
            <span key={i} className="mb-6 flex h-14 w-32 shrink-0 items-center justify-center rounded-xl border-2 border-[var(--brand)] font-mono text-xs text-[var(--brand)]" />
          ))}
        </div>
        <div className="relative mx-auto max-w-5xl px-4 pb-32 pt-8 md:pt-28">
          <p className="inline-flex items-center gap-2 rounded-full bg-[var(--brand)] px-3 py-1 text-sm font-bold text-[#14152B]"><Link2 aria-hidden className="size-4" /> Public log</p>
          <h1 className="mt-4 text-balance text-5xl leading-[1.02] md:text-7xl">Nothing here can be quietly changed.</h1>
          <p className="mt-4 max-w-2xl text-lg text-white/75">
            Every certificate ever issued is added here with the fingerprint of the entry before it. Rewrite or delete history and every later entry
            stops matching. It stores only fingerprints, never personal data.
          </p>
          <p className="mt-6 font-display text-6xl font-extrabold tabular-nums text-[var(--brand)]">{total}<span className="ml-3 text-xl font-bold text-white/70">entries and counting</span></p>
        </div>
      </section>
      <div className="mx-auto max-w-5xl px-4 py-10">


      <section aria-label="Check the chain" className="mt-6 rounded-[var(--radius-panel)] border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => shown && void check(shown)} disabled={!shown || shown.length === 0 || running}>
            <ShieldCheck /> {running ? "Checking..." : result ? "Verify again" : "Verify the whole chain in your browser"}
          </Button>
          {shown && shown.length > 1 && (
            <Button variant="outline" onClick={() => setTampered(tampered === null ? Math.max(0, Math.floor(shown.length / 2) - 1) : null)} disabled={running}>
              {tampered === null ? "Alter an entry (demo)" : "Undo the alteration"}
            </Button>
          )}
        </div>

        {running && progress && (
          <div className="mt-4" role="progressbar" aria-label="Re-computing the chain" aria-valuemin={0} aria-valuemax={progress.total} aria-valuenow={progress.done}>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${Math.round((progress.done / Math.max(1, progress.total)) * 100)}%` }} />
            </div>
            <p className="mt-1 text-xs text-muted-foreground tabular-nums">Entry {progress.done} of {progress.total}</p>
          </div>
        )}

        <p
          role="status"
          className={cn(
            "mt-4 inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium",
            result ? (result.ok ? "bg-verified-soft text-verified" : "bg-destructive/10 text-destructive") : "bg-muted text-muted-foreground",
          )}
        >
          {result ? (result.ok ? <CheckCircle2 aria-hidden className="size-4" /> : <AlertCircle aria-hidden className="size-4" />) : <Link2 aria-hidden className="size-4" />}
          {!shown || running
            ? shown
              ? "Re-computing on this device"
              : "Loading the log"
            : !result
              ? shown.length === 0
                ? "Nothing has been logged yet"
                : "Not checked on this device yet. Press the button and your browser will re-compute every link."
              : result.ok
                ? `Chain intact: ${shown.length} ${shown.length === 1 ? "entry" : "entries"} re-computed on this device${result.fromStart ? ", from the first entry" : ""}`
                : result.why === "link"
                  ? `Chain broken at entry ${bad! + 1}: it does not point at the entry before it`
                  : `Chain broken at entry ${bad! + 1}: its content no longer matches its hash`}
        </p>
        {tampered !== null && (
          <p className="mt-2 text-sm text-muted-foreground">One fingerprint was changed in your browser only. Nothing was sent to the registry.</p>
        )}
      </section>

      {!shown ? (
        <Skeleton className="mt-6 h-64 rounded-2xl" />
      ) : shown.length === 0 ? (
        <p className="mt-8 rounded-2xl border border-dashed border-border p-10 text-center text-muted-foreground">No certificates issued yet.</p>
      ) : (
        <ol className="mt-8 ml-3 space-y-3 border-l-2 border-border pl-6" aria-label="Log entries, newest first">
          {[...shown].reverse().slice(0, shownCount).map((e, r) => {
            const i = shown.length - 1 - r;
            const broken = bad !== null && i >= bad;
            return (
              <li key={e.id} className="relative">
                <span
                  aria-hidden
                  className={cn("absolute -left-[33px] top-5 size-3 rounded-full border-2 border-background", broken ? "bg-destructive" : result?.ok ? "bg-verified" : "bg-muted-foreground/50")}
                />
                <div className={cn("rounded-xl border bg-card p-4", broken ? "border-destructive/60" : "border-border")}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Link href={`/verify/${e.certificate_code}`} className="font-mono text-sm font-semibold text-primary hover:underline">
                      {e.certificate_code}
                    </Link>
                    <span className="flex items-center gap-3 text-xs text-muted-foreground">
                      {broken && (
                        <span className="inline-flex items-center gap-1 text-destructive">
                          <AlertCircle aria-hidden className="size-3.5" /> {i === bad ? "First mismatch" : "Follows a mismatch"}
                        </span>
                      )}
                      {e.issued_at}
                    </span>
                  </div>
                  <dl className="mt-2 grid gap-0.5 font-mono text-xs text-muted-foreground">
                    <div className="flex gap-2"><dt className="w-16 shrink-0">content</dt><dd className="break-all">{e.digest}</dd></div>
                    <div className="flex gap-2"><dt className="w-16 shrink-0">previous</dt><dd className="break-all">{e.prev_hash}</dd></div>
                    <div className="flex gap-2"><dt className="w-16 shrink-0 text-foreground"><Link2 aria-hidden className="mr-1 inline size-3" />entry</dt><dd className="break-all text-foreground">{e.entry_hash}</dd></div>
                  </dl>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {shown && shownCount < total && (
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button variant="outline" onClick={() => setVisible((v) => v + 50)}>Show 50 more entries</Button>
          <p className="text-sm text-muted-foreground tabular-nums">Showing the newest {shownCount} of {total}. The check above covers all {total}.</p>
        </div>
      )}
      </div>
    </div>
  );
}
