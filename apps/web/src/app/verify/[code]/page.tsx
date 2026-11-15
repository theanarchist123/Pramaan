"use client";

import { ShareRow } from "@/components/share-row";
import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BadgeCheck, Copy, Download, FileImage, FlaskConical, RotateCcw, Share2, ShieldAlert, ShieldQuestion, Layers } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Certificate, type CertificateData } from "@/components/certificate/certificate";
import { ScaledTilt } from "@/components/certificate/scaled-tilt";
import { CheckCascade, type CheckStep } from "@/components/motion/check-cascade";
import { SealLanding } from "@/components/motion/seal-landing";
import { toCertificateData, useCertificate, type CertificateDetail, type VerifyResult } from "@/hooks/use-certificate";
import { API_URL, api } from "@/lib/api";
import { rememberCheck } from "@/lib/recent-checks";
import { VERDICT_COPY, isCodeChar, suggestions, verdictOf, type Verdict } from "@/lib/verify-verdict";
import { cn } from "@/lib/utils";

type Claim = { field: string; value: string; status: string };

const TONE: Record<"verified" | "caution" | "seal" | "neutral", { bg: string; fg: string }> = {
  verified: { bg: "bg-verified-soft", fg: "text-verified" },
  caution: { bg: "bg-pending-soft", fg: "text-foreground" },
  seal: { bg: "bg-destructive/10", fg: "text-destructive" },
  neutral: { bg: "bg-muted", fg: "text-muted-foreground" },
};
const ICON: Record<Verdict, typeof BadgeCheck> = { valid: BadgeCheck, replaced: Layers, revoked: ShieldAlert, altered: ShieldAlert, not_found: ShieldQuestion };

export default function VerifyCode({ params }: { params: Promise<{ code: string }> }) {
  const { code: raw } = use(params);
  const code = decodeURIComponent(raw).toUpperCase();
  const { detail, verify, error } = useCertificate(code, true);
  const missing = error === "not_found" || (verify !== null && !detail && !verify.payload);

  if (missing) return <NotFound code={code} reason={verify?.reason} />;
  if (!detail || !verify) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12" aria-busy>
        <Skeleton className="h-24 rounded-2xl" />
        <Skeleton className="mt-6 aspect-[1123/794] w-full rounded-2xl" />
      </div>
    );
  }
  return <Result code={code} detail={detail} verify={verify} />;
}

const BAND: Record<"verified" | "caution" | "seal" | "neutral", string> = {
  verified: "bg-[var(--verified)] text-[var(--bond)]",
  caution: "bg-[var(--brand)] text-[var(--on-brand)]",
  seal: "bg-[var(--seal)] text-[var(--bond)]",
  neutral: "bg-[var(--ink)] text-[var(--bond)]",
};

function Banner({ verdict, verify }: { verdict: Verdict; verify?: VerifyResult | null }) {
  const copy = VERDICT_COPY[verdict];
  const Icon = ICON[verdict];
  return (
    <section className={cn("md:-mt-16", BAND[copy.tone])} role="status" data-nav-tone={copy.tone === "caution" ? "on-light" : "inverse"}>
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-6 px-4 pb-10 pt-8 md:pt-28">
        <SealLanding ring={verdict === "valid"}>
          <Icon className="size-20 md:size-24" aria-hidden />
        </SealLanding>
        <div className="min-w-0 flex-1">
          <h1 className="text-balance text-4xl leading-[1.05] md:text-6xl">{copy.title}</h1>
          <p className="mt-2 max-w-2xl text-lg opacity-90">{copy.sentence(verify)}</p>
          {verdict === "replaced" && verify?.superseded_by && (
            <Link className="mt-2 inline-block font-semibold underline" href={`/verify/${verify.superseded_by}`}>
              View the newer certificate
            </Link>
          )}
        </div>
        <Link href="/verify" className="inline-flex h-11 items-center rounded-full border-2 border-current px-5 text-sm font-bold">Check another</Link>
      </div>
    </section>
  );
}

function NotFound({ code, reason }: { code: string; reason?: string }) {
  const fixes = suggestions(code);
  return (
    <div>
      <Banner verdict="not_found" />
      <div className="mx-auto max-w-xl px-4 py-10">
      <p className="text-muted-foreground">{reason ?? `We have no certificate with the code ${code}.`}</p>
      {[...code.replace(/^PRM-/, "")].some((c) => !isCodeChar(c)) && (
        <p className="mt-3 text-sm">
          Codes never contain 0, 1, I, L, O or U, so this one has a character that was misread or mistyped. Check it against the document.
          {fixes.length > 0 && (
            <>
              {" "}Did you mean{" "}
              {fixes.map((f) => (
                <Link key={f} href={`/verify/${f}`} className="mr-2 font-mono text-primary underline">{f}</Link>
              ))}
              ?
            </>
          )}
        </p>
      )}
      <Button className="mt-6" variant="outline" render={<Link href="/verify" />} nativeButton={false}>Try another code</Button>
      </div>
    </div>
  );
}

function Result({ code, detail, verify }: { code: string; detail: CertificateDetail; verify: VerifyResult }) {
  const base = useMemo(() => toCertificateData(detail), [detail]);
  const verdict = verdictOf(verify, false);
  const [forging, setForging] = useState(false);
  const [name, setName] = useState(base?.full_name ?? "");
  const [claims, setClaims] = useState<Claim[]>(base?.claims ?? []);
  const [forged, setForged] = useState<VerifyResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => rememberCheck({ code, name: base?.full_name ?? "", at: new Date().toISOString() }), [code, base?.full_name]);

  const changed = forging && base !== null && (name !== base.full_name || claims.some((c, i) => c.value !== base.claims[i]?.value));
  const original = verify.payload;

  useEffect(() => {
    if (!changed || !original) {
      setForged(null);
      return;
    }
    setBusy(true);
    const t = setTimeout(() => {
      api<VerifyResult>("/v1/verify/check", { method: "POST", auth: false, json: { code, payload: { ...original, full_name: name, claims } } })
        .then(setForged)
        .catch(() => toast.error("Could not reach the registry"))
        .finally(() => setBusy(false));
    }, 150);
    return () => clearTimeout(t);
  }, [name, claims, changed, code, original]);

  const reset = () => {
    setName(base?.full_name ?? "");
    setClaims(base?.claims ?? []);
  };

  // The checks on the right ARE the registry's answers. While you forge, the first two rows are re-run against your edit.
  const live = changed && forged && !busy;
  const steps: CheckStep[] = [
    { ok: live ? forged.digest === verify.digest : verify.signature_ok, text: live ? "Recomputed the fingerprint of the content as edited" : "Recomputed the SHA-256 fingerprint of the signed content", sub: live ? forged.digest : verify.digest },
    { ok: live ? forged.valid : verify.signature_ok, text: `Checked the Ed25519 signature against the registry's public key (${verify.key_id})`, sub: verify.signature.slice(0, 44) + "..." },
    { ok: verify.chain_ok, text: verify.log_position ? `Found at position #${verify.log_position} of ${verify.log_size} in the public transparency log` : "Looked for it in the public transparency log", sub: verify.entry_hash ? `entry ${verify.entry_hash.slice(0, 32)}...` : "" },
    { ok: !verify.revoked, text: verify.revoked ? "This certificate has been revoked" : "Confirmed it has not been revoked", sub: "" },
  ];

  const preview: CertificateData | null = base ? { ...base, full_name: name, claims, digest: forged?.digest ?? base.digest } : null;
  const cracked = Boolean(changed && forged && !forged.valid && !busy);

  return (
    <div>
      <Banner verdict={verdict} verify={verify} />

      <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="min-w-0 rounded-[1.8rem] bg-[var(--stamp-tint)] p-3 sm:p-5">
          {preview ? (
            <div className="relative">
              <ScaledTilt tilt={!forging}>
                <Certificate data={preview} forceTamper={cracked} state={verdict === "revoked" ? { kind: "revoked" } : verdict === "replaced" ? { kind: "replaced" } : undefined} />
              </ScaledTilt>

            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-border p-10 text-center text-muted-foreground">
              The holder erased their data, so the content is no longer shown. Only the signed fingerprint remains in the log.
            </div>
          )}

          {preview && original && !original.redacted && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button variant={forging ? "default" : "outline"} aria-pressed={forging} onClick={() => { setForging(!forging); reset(); }}>
                <FlaskConical /> {forging ? "Stop editing" : "Edit as a forger"}
              </Button>
              {changed && <Button variant="ghost" onClick={reset}><RotateCcw /> Reset</Button>}
              <p className="text-xs text-muted-foreground">
                {forging ? "Change any field on the list below. The checks on the right re-run against your edit." : "See what happens when someone changes a letter."}
              </p>
            </div>
          )}

          {forging && preview && (
            <div className="mt-4 space-y-3 rounded-2xl border border-border bg-card p-4">
              <div>
                <label className="block text-sm font-medium" htmlFor="f-name">Name on the certificate</label>
                <Input id="f-name" value={name} onChange={(e) => setName(e.target.value)} className="h-10" />
              </div>
              {claims.map((c, i) => (
                <div key={i}>
                  <label className="block text-sm font-medium" htmlFor={`f-c${i}`}>Achievement {i + 1}</label>
                  <Input id={`f-c${i}`} value={c.value} className="h-10" onChange={(e) => setClaims(claims.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))} />
                </div>
              ))}
              <div aria-live="polite" className="text-sm">
                {!changed ? (
                  <p className="text-muted-foreground">Nothing changed yet. Try making yourself an award-winner.</p>
                ) : busy || !forged ? (
                  <p className="text-muted-foreground">Checking against the signature...</p>
                ) : (
                  <div className={cn("space-y-2 rounded-xl p-3", forged.valid ? "bg-verified-soft" : "bg-destructive/10")}>
                    <p className={cn("font-semibold", forged.valid ? "text-verified" : "text-destructive")}>{forged.valid ? "Still valid" : "Forgery detected"}</p>
                    <p>{forged.reason}</p>
                    {forged.changed_fields.length > 0 && (
                      <p>The registry pinpointed what you changed: {forged.changed_fields.map((f) => <code key={f} className="mx-0.5 rounded bg-background px-1.5 py-0.5 text-xs">{f}</code>)}</p>
                    )}
                    <DigestDiff a={verify.digest} b={forged.digest} />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="min-w-0 space-y-5">
          <section aria-label="How we checked" className="pop rounded-3xl bg-card p-5">
            <h2 className="text-2xl">How we checked</h2>
            <div className="mt-3"><CheckCascade key={live ? "live" : "base"} steps={steps} label="How we checked" /></div>
          </section>
          {preview && verdict !== "revoked" && verdict !== "altered" && <Actions code={code} detail={detail} />}
          {detail.profile && verdict !== "altered" && (
            <p className="text-sm text-muted-foreground">
              Holder: <Link className="text-foreground underline" href={`/p/${detail.profile.slug}`}>{detail.profile.full_name}</Link> · {detail.profile.headline || detail.profile.sector}
            </p>
          )}
        </div>
      </div>

      <YourselfSection verify={verify} />
      </div>
    </div>
  );
}

function Actions({ code, detail }: { code: string; detail: CertificateDetail }) {
  const url = typeof window !== "undefined" ? `${window.location.origin}/verify/${code}` : "";
  const issued = new Date(detail.issued_at);
  const linkedin =
    "https://www.linkedin.com/profile/add?" +
    new URLSearchParams({ startTask: "CERTIFICATION_NAME", name: "Pramaan Verified Achievement", organizationName: "Pramaan", issueYear: String(issued.getFullYear()), issueMonth: String(issued.getMonth() + 1), certUrl: url, certId: code });
  async function downloadJson() {
    try {
      const res = await fetch(`${API_URL}/v1/certificates/${encodeURIComponent(code)}`);
      if (!res.ok) throw new Error();
      const href = URL.createObjectURL(new Blob([await res.text()], { type: "application/json" }));
      Object.assign(document.createElement("a"), { href, download: `${code}.json` }).click();
      URL.revokeObjectURL(href);
    } catch {
      toast.error("Could not download the certificate file");
    }
  }
  return (
    <section aria-label="Download and share" className="rounded-2xl border border-border bg-card p-5">
      <h2 className="text-lg font-semibold">Keep or share it</h2>
      <p className="mt-1 text-xs text-muted-foreground">A printed copy can be altered; the online record cannot. Anyone can scan the code to check.</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Button variant="outline" render={<a href={`${API_URL}/v1/certificates/${code}/pdf`} download />} nativeButton={false}><Download /> PDF</Button>
        <Button variant="outline" render={<a href={`${API_URL}/v1/certificates/${code}/image.png`} download />} nativeButton={false}><FileImage /> Image</Button>
        <Button variant="outline" onClick={downloadJson} title="The signed certificate as JSON. The desktop app, or the drop box on the Verify page, can check it with no internet."><Download /> JSON (offline check)</Button>
        <ShareRow className="col-span-2" url={url} text="Check this Pramaan certificate:" />
        <Button variant="outline" className="col-span-2" render={<a href={linkedin} target="_blank" rel="noreferrer" />} nativeButton={false}><Share2 /> Add to LinkedIn</Button>
      </div>
    </section>
  );
}

function DigestDiff({ a, b }: { a: string; b: string }) {
  return (
    <div className="space-y-1 break-all font-mono text-[11px] leading-5">
      <p><span className="mr-2 text-muted-foreground">signed</span>{a}</p>
      <p>
        <span className="mr-2 text-muted-foreground">yours </span>
        {b.split("").map((ch, i) => (
          <span key={i} className={ch !== a[i] ? "rounded-sm bg-destructive/20 text-destructive" : ""}>{ch}</span>
        ))}
      </p>
    </div>
  );
}

function YourselfSection({ verify }: { verify: VerifyResult }) {
  const [lang, setLang] = useState<"python" | "javascript">("python");
  const payload = JSON.stringify(verify.payload ?? {}, null, 2);
  const python = `import base64, hashlib, json
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
  const js = `// Node 20+ or a current browser (WebCrypto Ed25519)
const payload = ${payload};
const canonical = (v) => v === null || typeof v !== "object" ? JSON.stringify(v)
  : Array.isArray(v) ? "[" + v.map(canonical).join(",") + "]"
  : "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + canonical(v[k])).join(",") + "}";
const b64 = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "=")), (c) => c.charCodeAt(0));

const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical(payload))));
const key = await crypto.subtle.importKey("raw", b64("${verify.public_key}"), { name: "Ed25519" }, false, ["verify"]);
console.log(await crypto.subtle.verify({ name: "Ed25519" }, key, b64("${verify.signature}"), digest) ? "authentic" : "ALTERED");`;
  return (
    <section aria-label="Verify it yourself" className="mt-10 rounded-3xl border border-border bg-card p-6">
      <h2 className="text-2xl font-semibold">Do not trust us: check it yourself</h2>
      <p className="mt-1 max-w-3xl text-muted-foreground">
        Nothing above is secret. Redo it with the registry&apos;s{" "}
        <a className="text-primary underline" href={`${API_URL}/.well-known/pramaan-keys.json`} target="_blank" rel="noreferrer">published public key</a>
        , and audit the <Link className="text-primary underline" href="/transparency">public transparency log</Link>.
      </p>
      <div role="tablist" aria-label="Language" className="mt-4 flex gap-1">
        {(["python", "javascript"] as const).map((l) => (
          <Button key={l} role="tab" aria-selected={lang === l} size="sm" variant={lang === l ? "default" : "outline"} onClick={() => setLang(l)}>
            {l === "python" ? "Python" : "JavaScript"}
          </Button>
        ))}
      </div>
      <pre tabIndex={0} className="mt-3 max-h-80 overflow-auto rounded-2xl bg-foreground p-4 text-[12px] leading-relaxed text-background">{lang === "python" ? python : js}</pre>
    </section>
  );
}
