"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import QRCode from "qrcode";
import { api, ApiError } from "@/lib/api";
import { Icon, PageHead, Pill } from "@/components/ui";

interface Status { enrolled: boolean; stepup_active: boolean; required: boolean }

async function copy(text: string) {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}

/** Authenticator-app enrolment (QR code or typed key), recovery codes (shown once), and the step-up code that unlocks sensitive actions.
 *  The QR code is drawn here in the browser from the key the server just issued; nothing is sent to a third party. */
export default function SecurityPage() {
  const router = useRouter();
  const [status, setStatus] = useState<Status | null>(null);
  const [secret, setSecret] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [qr, setQr] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [code, setCode] = useState("");
  const [rcode, setRcode] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");

  const load = () =>
    api<Status>("/v1/auth/mfa/status").then(setStatus).catch((e) => (e instanceof ApiError && e.status === 401 ? router.push("/login") : setError(e.message)));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let live = true;
    if (!secret) { setQr(""); return; }
    QRCode.toDataURL(secret.otpauth_uri, { margin: 1, width: 400, errorCorrectionLevel: "M" }).then((u) => live && setQr(u)).catch(() => live && setQr(""));
    return () => { live = false; };
  }, [secret]);

  async function run<T>(fn: () => Promise<T>, ok: string, after?: (r: T) => void) {
    setError(""); setMsg("");
    try {
      const r = await fn();
      after?.(r);
      setMsg(ok); setCode(""); setRcode(""); await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed");
    }
  }

  async function doCopy(label: string, text: string) {
    setCopied((await copy(text)) ? label : "");
    setTimeout(() => setCopied(""), 2000);
  }

  function download(codes: string[]) {
    const url = URL.createObjectURL(new Blob([`Pramaan Desk recovery codes\nEach works once. Keep them offline.\n\n${codes.join("\n")}\n`], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url; a.download = "pramaan-desk-recovery-codes.txt"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main style={{ maxWidth: 760 }}>
      <PageHead eyebrow="Your account" title="Security" lead="Staff sign-ins are protected by an authenticator app on your phone. It works offline and needs no Google account." />

      {recovery && (
        <div className="panel pop" role="alert">
          <h2 className="panel-title"><Icon name="key" /> Save these recovery codes now</h2>
          <p className="muted">Each works once if you lose your authenticator. They are not shown again. Keep them somewhere safe and offline.</p>
          <div className="codes" data-testid="recovery-codes">{recovery.map((c) => <span key={c}><code>{c}</code>{" "}</span>)}</div>
          <div className="row">
            <button type="button" className="secondary" onClick={() => doCopy("codes", recovery.join("\n"))}><Icon name="copy" size={16} /> {copied === "codes" ? "Copied" : "Copy"}</button>
            <button type="button" className="secondary" onClick={() => download(recovery)}><Icon name="file" size={16} /> Download</button>
            <button type="button" onClick={() => setRecovery(null)}>I have saved them</button>
          </div>
        </div>
      )}

      {status && (
        <div className="panel">
          <p style={{ margin: 0, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <span>Authenticator app: <strong>{status.enrolled ? "set up" : "not set up"}</strong>
              {status.enrolled && <> · step-up code {status.stepup_active ? "active" : "needed for sensitive actions"}</>}</span>
            <Pill tone={status.enrolled ? "ok" : "warn"}>{status.enrolled ? "Protected" : "Not protected yet"}</Pill>
          </p>

          {!status.enrolled && !secret && (
            <div style={{ marginTop: 16 }}>
              <p className="muted">It takes a minute. You will install an authenticator app, scan one picture, and type the 6 digits it shows.</p>
              <button onClick={async () => setSecret(await api("/v1/auth/mfa/enroll", { method: "POST" }))}>Set up authenticator</button>
            </div>
          )}

          {secret && (
            <div className="setup" style={{ marginTop: 18 }}>
              <div className="setup-step">
                <span className="setup-n">1</span>
                <div>
                  <strong>Install an authenticator app</strong>
                  <p className="muted" style={{ margin: "4px 0 0" }}>Any one works: Google Authenticator, Microsoft Authenticator, Authy, 1Password or Aegis. You do not need to sign in to anything.</p>
                </div>
              </div>
              <div className="setup-step">
                <span className="setup-n">2</span>
                <div>
                  <strong>Scan this picture with the app</strong>
                  <p className="muted" style={{ margin: "4px 0 10px" }}>Or type the key by hand. It is shown once.</p>
                  <div className="row" style={{ alignItems: "flex-start", gap: 20 }}>
                    {qr ? <img className="qr" src={qr} alt="QR code to add this account in your authenticator app" /> : <span className="muted">Drawing the code…</span>}
                    <div>
                      <div className="keybox">
                        <code>{secret.secret}</code>
                        <button type="button" className="secondary" style={{ height: 36 }} onClick={() => doCopy("key", secret.secret)}><Icon name="copy" size={15} /> {copied === "key" ? "Copied" : "Copy"}</button>
                      </div>
                      <p style={{ margin: "10px 0 0" }}><a href={secret.otpauth_uri}>On this phone? Open in authenticator</a></p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="setup-step">
                <span className="setup-n">3</span>
                <div>
                  <strong>Type the 6 digits it shows</strong>
                  <label htmlFor="code" style={{ marginTop: 8 }}>6-digit code</label>
                  <div className="row">
                    <div className="grow"><input id="code" className="otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} placeholder="000000" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></div>
                    <button disabled={code.length !== 6} onClick={() => run(() => api<{ recovery_codes: string[] }>("/v1/auth/mfa/confirm", { method: "POST", json: { code } }), "Authenticator set up", (r) => { setRecovery(r.recovery_codes); setSecret(null); })}>Finish set-up</button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {status.enrolled && (
            <>
              <label htmlFor="code">6-digit code</label>
              <div className="row">
                <div className="grow"><input id="code" className="otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} placeholder="000000" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></div>
                <button disabled={code.length !== 6} onClick={() => run(() => api("/v1/auth/mfa/stepup", { method: "POST", json: { code } }), "Confirmed for sensitive actions")}>Confirm</button>
              </div>
              <label htmlFor="rcode">Lost your authenticator? Use a recovery code</label>
              <div className="row">
                <div className="grow"><input id="rcode" placeholder="abcd-efgh" maxLength={9} value={rcode} onChange={(e) => setRcode(e.target.value)} /></div>
                <button className="secondary" disabled={rcode.length !== 9} onClick={() => run(() => api<{ recovery_codes_left: number }>("/v1/auth/mfa/recover", { method: "POST", json: { code: rcode } }), "Recovery code accepted")}>Use code</button>
              </div>
              <p><button className="secondary" onClick={() => run(() => api<{ recovery_codes: string[] }>("/v1/auth/mfa/recovery-codes", { method: "POST" }), "New recovery codes created", (r) => setRecovery(r.recovery_codes))}>Create new recovery codes</button>
                <span className="muted"> (needs a fresh authenticator code first; the old codes stop working)</span></p>
            </>
          )}
          {msg && <p className="notice" role="status"><Icon name="check" size={18} /><span>{msg}</span></p>}
          {error && <p className="alert" role="alert"><Icon name="alert" size={18} /><span>{error}</span></p>}
        </div>
      )}
    </main>
  );
}
