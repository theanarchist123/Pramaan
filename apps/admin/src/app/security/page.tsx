"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

interface Status { enrolled: boolean; stepup_active: boolean; required: boolean }

/** Authenticator-app enrolment, recovery codes (shown once), and the step-up code that unlocks sensitive actions. */
export default function SecurityPage() {
  const router = useRouter();
  const [status, setStatus] = useState<Status | null>(null);
  const [secret, setSecret] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [code, setCode] = useState("");
  const [rcode, setRcode] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const load = () =>
    api<Status>("/v1/auth/mfa/status").then(setStatus).catch((e) => (e instanceof ApiError && e.status === 401 ? router.push("/login") : setError(e.message)));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

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

  return (
    <main style={{ maxWidth: 560 }}>
      <h1>Security</h1>
      <p><Link href="/">← Review queue</Link></p>
      {recovery && (
        <div className="panel" role="alert">
          <strong>Save these recovery codes now.</strong>
          <p className="muted">Each works once if you lose your authenticator. They are not shown again. Keep them somewhere safe and offline.</p>
          <pre data-testid="recovery-codes" style={{ margin: 0 }}>{recovery.join("\n")}</pre>
          <p><button className="secondary" onClick={() => setRecovery(null)}>I have saved them</button></p>
        </div>
      )}
      {status && (
        <div className="panel">
          <p>Authenticator app: <strong>{status.enrolled ? "set up" : "not set up"}</strong>
            {status.enrolled && <> · step-up code {status.stepup_active ? "active" : "needed for sensitive actions"}</>}</p>
          {!status.enrolled && !secret && (
            <button onClick={async () => setSecret(await api("/v1/auth/mfa/enroll", { method: "POST" }))}>Set up authenticator</button>
          )}
          {secret && (
            <>
              <p>Add this account in your authenticator app (Google Authenticator, Authy, 1Password...), using the key below or the link on a phone. It is shown once.</p>
              <p><code>{secret.secret}</code></p>
              <p><a href={secret.otpauth_uri}>Open in authenticator</a></p>
            </>
          )}
          {(secret || status.enrolled) && (
            <>
              <label htmlFor="code">6-digit code</label>
              <div className="row">
                <div className="grow"><input id="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></div>
                {status.enrolled ? (
                  <button disabled={code.length !== 6} onClick={() => run(() => api("/v1/auth/mfa/stepup", { method: "POST", json: { code } }), "Confirmed for sensitive actions")}>Confirm</button>
                ) : (
                  <button disabled={code.length !== 6} onClick={() => run(() => api<{ recovery_codes: string[] }>("/v1/auth/mfa/confirm", { method: "POST", json: { code } }), "Authenticator set up", (r) => { setRecovery(r.recovery_codes); setSecret(null); })}>Finish set-up</button>
                )}
              </div>
            </>
          )}
          {status.enrolled && (
            <>
              <label htmlFor="rcode">Lost your authenticator? Use a recovery code</label>
              <div className="row">
                <div className="grow"><input id="rcode" placeholder="abcd-efgh" maxLength={9} value={rcode} onChange={(e) => setRcode(e.target.value)} /></div>
                <button className="secondary" disabled={rcode.length !== 9} onClick={() => run(() => api<{ recovery_codes_left: number }>("/v1/auth/mfa/recover", { method: "POST", json: { code: rcode } }), "Recovery code accepted")}>Use code</button>
              </div>
              <p><button className="secondary" onClick={() => run(() => api<{ recovery_codes: string[] }>("/v1/auth/mfa/recovery-codes", { method: "POST" }), "New recovery codes created", (r) => setRecovery(r.recovery_codes))}>Create new recovery codes</button>
                <span className="muted"> (needs a fresh authenticator code first; the old codes stop working)</span></p>
            </>
          )}
          {msg && <p role="status">{msg}</p>}
          {error && <p className="err" role="alert">{error}</p>}
        </div>
      )}
    </main>
  );
}
