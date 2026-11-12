"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { CheckCascade, type CheckStep } from "@/components/motion/check-cascade";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { VerifyResult } from "@/hooks/use-certificate";

/**
 * The home hero's proof: not a picture of the product but the product. It checks the registry's most recent real certificate, here
 * and now, and lists what it found (the same cascade as the Verify page). If the registry is empty or unreachable it says so, and
 * shows what a check consists of without pretending a result.
 */
export function ProofTable() {
  const [result, setResult] = useState<VerifyResult | null | "none">(null);

  useEffect(() => {
    let live = true;
    api<{ certificate_code: string }[]>("/v1/transparency?limit=1", { auth: false })
      .then(async (l) => {
        const code = l[0]?.certificate_code;
        if (!code) return live && setResult("none");
        const v = await api<VerifyResult>(`/v1/verify/${encodeURIComponent(code)}`, { auth: false });
        if (live) setResult(v);
      })
      .catch(() => live && setResult("none"));
    return () => {
      live = false;
    };
  }, []);

  const steps: CheckStep[] =
    result && result !== "none"
      ? [
          { ok: result.signature_ok, text: "Recomputed the SHA-256 fingerprint of the signed content", sub: result.digest },
          { ok: result.signature_ok, text: `Checked the Ed25519 signature against the registry's public key (${result.key_id})` },
          { ok: result.chain_ok, text: result.log_position ? `Found at position #${result.log_position} of ${result.log_size} in the public log` : "Looked for it in the public log" },
          { ok: !result.revoked, text: result.revoked ? "This certificate has been revoked" : "Confirmed it has not been revoked" },
        ]
      : [];

  return (
    <section aria-label="A live check of the registry's latest certificate" className="rounded-3xl border border-border bg-card p-5 shadow-xl shadow-primary/5">
      <p className="text-sm font-medium">Checked just now</p>
      <p className="text-xs text-muted-foreground">The latest certificate in the registry, checked live against the registry when this page loaded, not a recording.</p>
      <div className="mt-4 min-h-40">
        {result === null && <p className="text-sm text-muted-foreground" role="status">Checking...</p>}
        {result === "none" && (
          <p className="text-sm text-muted-foreground">
            There is no certificate to check yet, or the registry could not be reached. Every certificate gets these four checks: fingerprint,
            signature, public log, revocation.
          </p>
        )}
        {result && result !== "none" && (
          <>
            <p className="mb-3 font-mono text-sm">{result.code}</p>
            <CheckCascade steps={steps} label="Checks on the latest certificate" />
          </>
        )}
      </div>
      {result && result !== "none" && (
        <Button variant="outline" className="mt-4" render={<Link href={`/verify/${result.code}`} />} nativeButton={false}>
          Open this check <ArrowRight />
        </Button>
      )}
    </section>
  );
}
