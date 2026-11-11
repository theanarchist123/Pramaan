"use client";

import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";
import { Certificate } from "@/components/certificate/certificate";
import { ScaledTilt } from "@/components/certificate/scaled-tilt";
import { toCertificateData, useCertificate, type VerifyResult } from "@/hooks/use-certificate";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * The home page's proof table (spec 6.1): a REAL certificate on the desk with an editable name. Change a letter and the registry is asked
 * whether the signature still holds; it does not, so the seal cracks. Nothing here is staged: the answer comes from /v1/verify/check.
 * It shows the newest certificate that checks out (a revoked one is real, but a landing page leads with a pass).
 */
export function DeskCertificate() {
  const [code, setCode] = useState<string | null>(null);
  const [none, setNone] = useState(false);

  useEffect(() => {
    let live = true;
    api<{ certificate_code: string }[]>("/v1/transparency?limit=8", { auth: false })
      .then(async (l) => {
        for (const e of l) {
          const v = await api<VerifyResult>(`/v1/verify/${encodeURIComponent(e.certificate_code)}`, { auth: false });
          if (v.valid && !v.revoked) return live && setCode(e.certificate_code);
        }
        if (live) setNone(true);
      })
      .catch(() => live && setNone(true));
    return () => {
      live = false;
    };
  }, []);

  if (none) {
    return (
      <div className="paper-object p-6 text-sm">
        <p className="font-heading text-xl font-semibold">A certificate will sit here</p>
        <p className="mt-1 text-muted-foreground">There is nothing to show yet, or the registry could not be reached. Once one is issued you can change a letter in its name and watch the seal crack.</p>
      </div>
    );
  }
  return code ? <Desk code={code} /> : <div className="aspect-[1123/794] animate-pulse rounded-[var(--radius-sheet)] bg-muted motion-reduce:animate-none" aria-label="Loading a certificate" />;
}

function Desk({ code }: { code: string }) {
  const { detail, verify } = useCertificate(code, true);
  const base = detail ? toCertificateData(detail) : null;
  const [name, setName] = useState<string | null>(null);
  const [answer, setAnswer] = useState<VerifyResult | null>(null);
  const shown = name ?? base?.full_name ?? "";
  const changed = base !== null && name !== null && name !== base.full_name;

  useEffect(() => {
    if (!changed || !verify?.payload) {
      setAnswer(null);
      return;
    }
    const t = setTimeout(() => {
      api<VerifyResult>("/v1/verify/check", { method: "POST", auth: false, json: { code, payload: { ...verify.payload, full_name: name } } })
        .then(setAnswer)
        .catch(() => setAnswer(null));
    }, 200);
    return () => clearTimeout(t);
  }, [changed, name, code, verify?.payload]);

  const cracked = changed && answer !== null && !answer.valid;

  if (!base) return <div className="aspect-[1123/794] animate-pulse rounded-[var(--radius-sheet)] bg-muted motion-reduce:animate-none" aria-label="Loading a certificate" />;
  return (
    <div className="rounded-[var(--radius-sheet)] border border-border bg-[color-mix(in_srgb,var(--ink)_6%,var(--bond))] p-3 sm:p-4">
      <ScaledTilt tilt={!changed}>
        <Certificate data={{ ...base, full_name: shown }} forceTamper={cracked} />
      </ScaledTilt>
      <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
        <label className="text-sm">
          <span className="font-medium">Try to forge it: change a letter in the name</span>
          <input
            value={shown}
            onChange={(e) => setName(e.target.value)}
            spellCheck={false}
            className="mt-1 block h-10 w-full rounded-md border border-input bg-background px-3 font-heading text-lg outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/50"
          />
        </label>
        <p
          role="status"
          className={cn("inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium", cracked ? "bg-destructive/10 text-destructive" : "bg-verified-soft text-verified")}
        >
          {cracked ? <AlertCircle aria-hidden className="size-4" /> : <CheckCircle2 aria-hidden className="size-4" />}
          {cracked ? "Signature broken: the registry refuses it" : changed ? "Checking..." : "Signature valid: this is the real name"}
        </p>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        This is a real certificate from the registry, not a mock-up. Anything you type here is checked by the registry and never saved.
      </p>
    </div>
  );
}
