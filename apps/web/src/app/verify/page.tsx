"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, FileUp, Keyboard, ScanLine, ShieldCheck } from "lucide-react";
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
    <div className="-mt-28 md:-mt-16">
      <section className="bg-[var(--tile1)] text-[var(--tile1i)]">
        <div className="mx-auto max-w-6xl px-4 pb-28 pt-36 md:pt-28">
          <p className="inline-flex items-center gap-2 rounded-full border-2 border-current px-3 py-1 text-sm font-bold">
            <ShieldCheck aria-hidden className="size-4" /> No account needed
          </p>
          <h1 className="mt-4 max-w-3xl text-balance text-5xl leading-[1.02] md:text-7xl">Is this certificate real?</h1>
          <p className="mt-4 max-w-2xl text-lg">Check that a Pramaan certificate is genuine and unchanged. It takes a few seconds.</p>
        </div>
      </section>

      <div className="relative z-10 mx-auto -mt-20 max-w-6xl px-4">
        <section aria-label="Check a certificate" className="pop grid gap-0 overflow-hidden rounded-[1.8rem] bg-card md:grid-cols-3">
          <div className="min-w-0 p-5 md:p-6">
            <h2 className="flex items-center gap-2 font-display text-xl font-bold"><Keyboard aria-hidden className="size-5" /> Type the code</h2>
            <p className="mb-3 mt-1 text-sm text-muted-foreground">Printed under the QR code, starting PRM-.</p>
            <CodeInput value={value} bad={bad} onChange={setValue} onComplete={go} onReject={setBad} />
            {hint.length > 0 && (
              <p className="mt-2 text-sm">
                Did you mean{" "}
                {hint.map((h) => (
                  <Button key={h} variant="link" className="h-auto p-0 font-mono" onClick={() => go(h)}>{h}</Button>
                ))}
                ?
              </p>
            )}
            <Button className="mt-4" size="lg" disabled={value.length !== 10} onClick={() => go(`PRM-${value}`)}>
              Check it <ArrowRight />
            </Button>
          </div>
          <div className="min-w-0 border-t border-border p-5 md:border-l md:border-t-0 md:p-6">
            <h2 className="flex items-center gap-2 font-display text-xl font-bold"><ScanLine aria-hidden className="size-5" /> Scan the QR</h2>
            <p className="mb-3 mt-1 text-sm text-muted-foreground">Point your camera at the code.</p>
            <Scanner onCode={go} />
          </div>
          <div className="min-w-0 border-t border-border bg-[var(--stamp-tint)] p-5 md:border-l md:border-t-0 md:p-6">
            <h2 className="flex items-center gap-2 font-display text-xl font-bold"><FileUp aria-hidden className="size-5" /> Drop a file</h2>
            <p className="mb-3 mt-1 text-sm text-muted-foreground">Have the certificate file? Check it without the internet.</p>
            <FileDrop />
          </div>
        </section>
      </div>

      <section aria-label="What we check" className="mx-auto max-w-6xl px-4 pt-14">
        <h2 className="text-3xl md:text-4xl">Five checks, every time</h2>
        <ol className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {CHECKS.map(([name, detail], i) => (
            <li key={name} className="rounded-[1.3rem] border border-border bg-card p-4">
              <span className="mb-3 flex size-9 items-center justify-center rounded-xl font-display text-lg font-extrabold" style={{ background: `var(--tile${(i % 6) + 1})`, color: `var(--tile${(i % 6) + 1}i)` }}>{i + 1}</span>
              <p className="font-semibold leading-snug">{name}</p>
              <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-label="Recent checks" className="mx-auto max-w-6xl px-4 py-14">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-2xl md:text-3xl">Recent checks on this device</h2>
          {recent.length > 0 && <Button variant="ghost" size="sm" onClick={() => { clearRecent(); setRecent([]); }}>Clear</Button>}
        </div>
        {recent.length === 0 ? (
          <p className="mt-3 rounded-2xl border-2 border-dashed border-border p-6 text-muted-foreground">
            Nothing yet. Checks you make are listed here, kept only in this browser.
            {sample && <> Want to see a result first? <Link className="font-semibold text-foreground underline" href={`/verify/${sample}`}>Try a real, recent certificate</Link>.</>}
          </p>
        ) : (
          <ul className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((r) => (
              <li key={r.code}>
                <Link href={`/verify/${r.code}`} className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-card px-4 py-3 hover:-translate-y-0.5">
                  <span className="truncate font-semibold">{r.name || r.code}</span>
                  <span className="font-mono text-xs text-muted-foreground">{r.code}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
