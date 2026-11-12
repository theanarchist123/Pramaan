"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Circle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CodeInput } from "@/components/verify/code-input";
import { FileDrop } from "@/components/verify/file-drop";
import { Scanner } from "@/components/verify/scanner";
import { api } from "@/lib/api";
import { clearRecent, readRecent, type RecentCheck } from "@/lib/recent-checks";
import { suggestions } from "@/lib/verify-verdict";

const CHECKS = [
  ["Content fingerprint", "SHA-256 of what was signed, recomputed"],
  ["Registry signature", "Ed25519, against the registry's published key"],
  ["Signing key", "Which key signed it, and that the registry publishes it"],
  ["Public log position", "Found in the hash-chained transparency log"],
  ["Revocation", "Whether the registry has withdrawn it"],
] as const;

/** Verify: the page is never empty. It says what will be checked, and offers every way in: typing, scanning, or a file. */
export default function VerifyLookup() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [bad, setBad] = useState("");
  const [recent, setRecent] = useState<RecentCheck[]>([]);
  const [sample, setSample] = useState<string | null>(null);

  // Opened through the browser's share sheet (see manifest share_target): find a certificate code in what was shared and go straight to the check.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const shared = [q.get("url"), q.get("text"), q.get("title")].filter(Boolean).join(" ");
    const m = /PRM-[A-Z0-9-]{4,32}/i.exec(shared);
    if (m) router.replace(`/verify/${encodeURIComponent(m[0].toUpperCase())}`);
  }, [router]);

  useEffect(() => {
    setRecent(readRecent());
    api<{ certificate_code: string }[]>("/v1/transparency?limit=1", { auth: false }).then((l) => setSample(l[0]?.certificate_code ?? null)).catch(() => {});
  }, []);

  const go = (code: string) => router.push(`/verify/${encodeURIComponent(code.toUpperCase())}`);
  const hint = suggestions(`PRM-${value}`);

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="font-heading text-4xl font-semibold">Verify a certificate</h1>
      <p className="mt-2 max-w-2xl text-muted-foreground">Check that a Pramaan certificate is genuine and unchanged. It takes a few seconds and needs no account.</p>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <section aria-label="Enter a certificate" className="min-w-0 space-y-5 rounded-2xl border border-border bg-card p-4 sm:p-5">
          <div>
            <h2 className="text-sm font-medium text-muted-foreground">Type or paste the code</h2>
            <div className="mt-2">
              <CodeInput
                value={value}
                bad={bad}
                onChange={setValue}
                onComplete={go}
                onReject={setBad}
              />
            </div>
            {hint.length > 0 && (
              <p className="mt-2 text-sm">
                Did you mean{" "}
                {hint.map((h) => (
                  <Button key={h} variant="link" className="h-auto p-0 font-mono" onClick={() => go(h)}>{h}</Button>
                ))}
                ?
              </p>
            )}
            <Button className="mt-3" disabled={value.length !== 10} onClick={() => go(`PRM-${value}`)}>
              Verify
            </Button>
          </div>
          <div className="border-t border-border pt-4">
            <h2 className="mb-2 text-sm font-medium text-muted-foreground">Or scan the QR code</h2>
            <Scanner onCode={go} />
          </div>
          <div className="border-t border-border pt-4">
            <FileDrop />
          </div>
        </section>

        <aside className="min-w-0 space-y-5">
          <section aria-label="What we check" className="rounded-2xl border border-border bg-card p-5">
            <h2 className="text-lg font-semibold">What we check</h2>
            <ul className="mt-3 space-y-3">
              {CHECKS.map(([name, detail]) => (
                <li key={name} className="flex gap-3">
                  <Circle className="mt-1 size-3.5 shrink-0 text-muted-foreground" aria-hidden />
                  <div>
                    <p className="text-sm font-medium">{name}</p>
                    <p className="text-xs text-muted-foreground">{detail}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section aria-label="Recent checks" className="rounded-2xl border border-border bg-card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Recent checks on this device</h2>
              {recent.length > 0 && (
                <Button variant="ghost" size="sm" onClick={() => { clearRecent(); setRecent([]); }}>Clear</Button>
              )}
            </div>
            {recent.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">Nothing yet. Checks you make are listed here, kept only in this browser.</p>
            ) : (
              <ul className="mt-2 space-y-1">
                {recent.map((r) => (
                  <li key={r.code}>
                    <Link href={`/verify/${r.code}`} className="flex justify-between gap-3 rounded-md px-2 py-1 text-sm hover:bg-muted">
                      <span className="truncate">{r.name || r.code}</span>
                      <span className="font-mono text-xs text-muted-foreground">{r.code}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {sample && (
            <p className="text-sm text-muted-foreground">
              Want to see a result first?{" "}
              <Link className="text-primary underline" href={`/verify/${sample}`}>Try a real, recent certificate</Link>.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}
