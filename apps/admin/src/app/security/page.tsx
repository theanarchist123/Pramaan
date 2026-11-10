"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

interface Status { enrolled: boolean; stepup_active: boolean; required: boolean }

/** Authenticator-app enrolment (mandatory for staff) and the step-up code that unlocks sensitive actions. */
export default function SecurityPage() {
  const router = useRouter();
  const [status, setStatus] = useState<Status | null>(null);
  const [secret, setSecret] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const load = () =>
    api<Status>("/v1/auth/mfa/status").then(setStatus).catch((e) => (e instanceof ApiError && e.status === 401 ? router.push("/login") : setError(e.message)));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(path: string, ok: string) {
    setError(""); setMsg("");
    try {
      await api(path, { method: "POST", json: { code } });
      setMsg(ok); setCode(""); setSecret(null); await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed");
    }
  }

  return (
    <main style={{ maxWidth: 520 }}>
      <h1>Security</h1>
      <p><Link href="/">← Review queue</Link></p>
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
                <button disabled={code.length !== 6} onClick={() => run(status.enrolled ? "/v1/auth/mfa/stepup" : "/v1/auth/mfa/confirm", status.enrolled ? "Confirmed for sensitive actions" : "Authenticator set up")}>
                  {status.enrolled ? "Confirm" : "Finish set-up"}
                </button>
              </div>
            </>
          )}
          {msg && <p role="status">{msg}</p>}
          {error && <p className="err" role="alert">{error}</p>}
        </div>
      )}
    </main>
  );
}
