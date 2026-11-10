"use client";

import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import {
  BadgeCheck, Check, Copy, Download, FileImage, FlaskConical, RotateCcw, Share2, ShieldAlert, X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Certificate, type CertificateData } from "@/components/certificate/certificate";
import { ScaledTilt } from "@/components/certificate/scaled-tilt";
import { toCertificateData, useCertificate, type CertificateDetail, type VerifyResult } from "@/hooks/use-certificate";
import { API_URL, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Claim = { field: string; value: string; status: string };

export default function VerifyCode({ params }: { params: Promise<{ code: string }> }) {
  const { code: raw } = use(params);
  const code = decodeURIComponent(raw).toUpperCase();
  const { detail, verify, error } = useCertificate(code, true);

  if (error === "not_found" || (verify && !detail && !verify.payload)) return <NotFound code={code} reason={verify?.reason} />;
  if (!detail || !verify) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12">
        <Skeleton className="h-24 rounded-2xl" />
        <Skeleton className="mt-6 aspect-[1123/794] w-full rounded-2xl" />
      </div>
    );
  }
  return <Verified code={code} detail={detail} verify={verify} />;
}

function NotFound({ code, reason }: { code: string; reason?: string }) {
  return (
    <div className="mx-auto max-w-xl px-4 py-20 text-center">
      <ShieldAlert className="mx-auto size-14 text-destructive" />
      <h1 className="mt-4 text-3xl font-semibold">No such certificate</h1>
      <p className="mt-2 text-muted-foreground">{reason ?? `We have no certificate with the code ${code}.`}</p>
      <p className="mt-1 text-sm text-muted-foreground">If you were handed this code, treat the document as unverified.</p>
      <Button className="mt-6" variant="outline" render={<Link href="/verify" />} nativeButton={false}>Try another code</Button>
    </div>
  );
}

function Verified({ code, detail, verify }: { code: string; detail: CertificateDetail; verify: VerifyResult }) {
  const { t } = useI18n();
  const base = useMemo(() => toCertificateData(detail), [detail]);
  const verdict: "ok" | "revoked" | "bad" = verify.valid ? "ok" : verify.revoked ? "revoked" : "bad";

  const steps = [
    { ok: verify.signature_ok, text: "Recomputed the SHA-256 fingerprint of the signed content", sub: verify.digest },
    { ok: verify.signature_ok, text: `Verified the Ed25519 signature with the registry's public key (${verify.key_id})`, sub: verify.signature.slice(0, 44) + "…" },
    {
      ok: verify.chain_ok,
      text: verify.log_position ? `Found at position #${verify.log_position} of ${verify.log_size} in the public transparency log` : "Looked for it in the public transparency log",
      sub: verify.entry_hash ? `entry ${verify.entry_hash.slice(0, 32)}…` : "",
    },
    { ok: !verify.revoked, text: verify.revoked ? "This certificate has been revoked" : "Confirmed it has not been revoked", sub: "" },
  ];

  const tone = {
    ok: { bg: "bg-verified-soft", fg: "text-verified", title: t("verify.authentic"), Icon: BadgeCheck },
    revoked: { bg: "bg-pending-soft", fg: "text-foreground", title: t("verify.revoked"), Icon: ShieldAlert },
    bad: { bg: "bg-destructive/10", fg: "text-destructive", title: t("verify.cannot"), Icon: ShieldAlert },
  }[verdict];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className={cn("flex items-center gap-4 rounded-2xl p-5", tone.bg)}
        role="status"
      >
        <motion.span initial={{ scale: 0.3, rotate: -40 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 260, damping: 14, delay: 0.15 }}>
          <tone.Icon className={cn("size-12", tone.fg)} />
        </motion.span>
        <div>
          <h1 className="text-3xl font-semibold">{tone.title}</h1>
          <p className="text-muted-foreground">{verify.reason}</p>
        </div>
      </motion.div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          {base ? (
            <ScaledTilt>
              <Certificate data={base} />
            </ScaledTilt>
          ) : (
            <div className="rounded-2xl border border-dashed border-border p-10 text-center text-muted-foreground">
              The holder erased their data, so the content is no longer shown. Only the signed fingerprint remains in the log.
            </div>
          )}
          <p className="mt-2 text-center text-xs text-muted-foreground">Move your pointer over the certificate. The artwork is generated from its fingerprint.</p>
        </div>

        <div className="min-w-0 space-y-5">
          <section aria-label="How we checked" className="rounded-2xl border border-border bg-card p-5">
            <h2 className="text-lg font-semibold">{t("verify.how")}</h2>
            <ol className="mt-3 space-y-3">
              {steps.map((s, i) => (
                <motion.li key={i} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.35 }} className="flex gap-3">
                  <span className={cn("mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full", s.ok ? "bg-verified text-background" : "bg-destructive text-background")}>
                    {s.ok ? <Check className="size-3.5" /> : <X className="size-3.5" />}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm">{s.text}</p>
                    {s.sub && <p className="mt-0.5 break-all font-mono text-[10.5px] text-muted-foreground">{s.sub}</p>}
                  </div>
                </motion.li>
              ))}
            </ol>
          </section>

          {base && verify.valid && <Actions code={code} detail={detail} />}

          {detail.profile && verify.valid && (
            <p className="text-sm text-muted-foreground">
              Holder: <span className="text-foreground">{detail.profile.full_name}</span> · {detail.profile.headline || detail.profile.sector}
            </p>
          )}
        </div>
      </div>

      {base && verify.payload && !verify.payload.redacted && <TamperLab code={code} base={base} verify={verify} />}
      <OfflineVerify verify={verify} />
    </div>
  );
}

function Actions({ code, detail }: { code: string; detail: CertificateDetail }) {
  const { t } = useI18n();
  const url = typeof window !== "undefined" ? `${window.location.origin}/verify/${code}` : "";
  const issued = new Date(detail.issued_at);
  const linkedin =
    "https://www.linkedin.com/profile/add?" +
    new URLSearchParams({
      startTask: "CERTIFICATION_NAME", name: "Pramaan Verified Achievement", organizationName: "Pramaan",
      issueYear: String(issued.getFullYear()), issueMonth: String(issued.getMonth() + 1), certUrl: url, certId: code,
    });
  return (
    <section aria-label="Share and download" className="rounded-2xl border border-border bg-card p-5">
      <h2 className="text-lg font-semibold">{t("verify.keep")}</h2>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Button variant="outline" render={<a href={`${API_URL}/v1/certificates/${code}/pdf`} download />} nativeButton={false}><Download /> PDF</Button>
        <Button variant="outline" render={<a href={`${API_URL}/v1/certificates/${code}/image.png`} download />} nativeButton={false}><FileImage /> Image</Button>
        <Button
          variant="outline"
          title="The signed certificate as JSON. The Pramaan desktop app can verify it with no internet."
          onClick={async () => {
            try {
              const res = await fetch(`${API_URL}/v1/certificates/${encodeURIComponent(code)}`);
              if (!res.ok) throw new Error();
              const href = URL.createObjectURL(new Blob([await res.text()], { type: "application/json" }));
              const a = Object.assign(document.createElement("a"), { href, download: `${code}.json` });
              a.click();
              URL.revokeObjectURL(href);
            } catch {
              toast.error("Couldn't download the certificate file");
            }
          }}
        ><Download /> JSON (offline check)</Button>
        <Button variant="outline" onClick={() => navigator.clipboard.writeText(url).then(() => toast.success("Verification link copied"))}><Copy /> Copy link</Button>
        <Button variant="outline" render={<a href={linkedin} target="_blank" rel="noreferrer" />} nativeButton={false}><Share2 /> Add to LinkedIn</Button>
      </div>
    </section>
  );
}

function DigestDiff({ a, b }: { a: string; b: string }) {
  return (
    <div className="space-y-1 font-mono text-[11px] leading-5 break-all">
      <p><span className="mr-2 text-muted-foreground">signed  </span>{a}</p>
      <p>
        <span className="mr-2 text-muted-foreground">yours   </span>
        {b.split("").map((ch, i) => (
          <span key={i} className={ch !== a[i] ? "rounded-sm bg-destructive/20 text-destructive" : ""}>{ch}</span>
        ))}
      </p>
    </div>
  );
}

function TamperLab({ code, base, verify }: { code: string; base: CertificateData; verify: VerifyResult }) {
  const { t } = useI18n();
  const original = verify.payload!;
  const [name, setName] = useState(base.full_name);
  const [claims, setClaims] = useState<Claim[]>(base.claims);
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [busy, setBusy] = useState(false);

  const changed = name !== base.full_name || claims.some((c, i) => c.value !== base.claims[i]?.value);

  useEffect(() => {
    if (!changed) {
      setResult(null);
      return;
    }
    setBusy(true);
    const t = setTimeout(() => {
      api<VerifyResult>("/v1/verify/check", {
        method: "POST", auth: false,
        json: { code, payload: { ...original, full_name: name, claims } },
      })
        .then(setResult)
        .catch(() => toast.error("Couldn't reach the registry"))
        .finally(() => setBusy(false));
    }, 450);
    return () => clearTimeout(t);
  }, [name, claims, changed, code, original]);

  const reset = () => {
    setName(base.full_name);
    setClaims(base.claims);
  };

  const preview: CertificateData = { ...base, full_name: name, claims, digest: result?.digest ?? base.digest };

  return (
    <section aria-label="Try to tamper" className="mt-10 rounded-3xl border border-border bg-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold"><FlaskConical className="size-6 text-primary" /> {t("verify.forge")}</h2>
          <p className="mt-1 max-w-2xl text-muted-foreground">
            Edit any field below, as a forger would. The registry re-checks the changed content against the original signature — and the artwork, which is drawn from the fingerprint, changes completely.
          </p>
        </div>
        {changed && <Button variant="outline" onClick={reset}><RotateCcw /> Reset</Button>}
      </div>

      <div className="mt-5 grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <label className="block text-sm font-medium" htmlFor="t-name">Name on the certificate</label>
          <Input id="t-name" value={name} onChange={(e) => setName(e.target.value)} className="h-10" />
          {claims.map((c, i) => (
            <div key={i}>
              <label className="block text-sm font-medium" htmlFor={`t-c${i}`}>Achievement {i + 1}</label>
              <Input id={`t-c${i}`} value={c.value} className="h-10"
                onChange={(e) => setClaims(claims.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))} />
            </div>
          ))}
        </div>

        <div aria-live="polite">
          <AnimatePresence mode="wait">
            {!changed ? (
              <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="rounded-2xl border border-dashed border-border p-6 text-sm text-muted-foreground">
                Nothing changed yet. Try making yourself an award-winner.
              </motion.div>
            ) : result && !busy ? (
              <motion.div key="res" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className={cn("space-y-3 rounded-2xl p-4", result.valid ? "bg-verified-soft" : "bg-destructive/10")}>
                <p className={cn("flex items-center gap-2 text-lg font-semibold", result.valid ? "text-verified" : "text-destructive")}>
                  {result.valid ? <BadgeCheck /> : <ShieldAlert />} {result.valid ? "Still valid" : "Forgery detected"}
                </p>
                <p className="text-sm">{result.reason}</p>
                {result.changed_fields.length > 0 && (
                  <p className="text-sm">
                    The registry pinpointed what you changed:{" "}
                    {result.changed_fields.map((f) => (
                      <code key={f} className="mx-0.5 rounded bg-background px-1.5 py-0.5 text-xs">{f}</code>
                    ))}
                  </p>
                )}
                <DigestDiff a={verify.digest} b={result.digest} />
              </motion.div>
            ) : (
              <motion.div key="busy" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="p-6 text-sm text-muted-foreground">Checking against the signature…</motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <div className="mt-6">
        <ScaledTilt tilt={false}>
          <Certificate data={preview} forceTamper={Boolean(changed && result && !result.valid && !busy)} />
        </ScaledTilt>
      </div>
    </section>
  );
}

function OfflineVerify({ verify }: { verify: VerifyResult }) {
  const { t } = useI18n();
  const payload = JSON.stringify(verify.payload ?? {}, null, 2);
  const snippet = `import base64, hashlib, json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

b64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
payload = json.loads('''${payload}''')

digest = hashlib.sha256(
    json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
).digest()

Ed25519PublicKey.from_public_bytes(b64("${verify.public_key}")).verify(
    b64("${verify.signature}"), digest
)  # raises InvalidSignature if anything was altered
print("authentic")`;
  return (
    <section aria-label="Verify it yourself" className="mt-10 rounded-3xl border border-border bg-card p-6">
      <h2 className="text-2xl font-semibold">{t("verify.yourself")}</h2>
      <p className="mt-1 max-w-3xl text-muted-foreground">
        The check above needs nothing secret. Anyone can redo it offline with the registry&apos;s{" "}
        <a className="text-primary underline" href={`${API_URL}/.well-known/pramaan-keys.json`} target="_blank" rel="noreferrer">published public key</a>
        , and audit the{" "}
        <Link className="text-primary underline" href="/transparency">public transparency log</Link>.
      </p>
      <pre tabIndex={0} className="mt-4 max-h-80 overflow-auto rounded-2xl bg-foreground p-4 text-[12px] leading-relaxed text-background">{snippet}</pre>
    </section>
  );
}
