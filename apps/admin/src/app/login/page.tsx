"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [needCode, setNeedCode] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await api<{ mfa_enrolled: boolean; mfa_required: boolean }>("/v1/admin/auth/login", { method: "POST", json: { email, password, code } });
      // Straight to set-up only when it is mandatory and not done; otherwise the queue (set-up stays one click away).
      router.push(r.mfa_required && !r.mfa_enrolled ? "/security" : "/");
    } catch (err) {
      if (err instanceof ApiError && err.code === "mfa_code_required") {
        setNeedCode(true); // not an error: the password was right and the authenticator code is the next step
        return;
      }
      setError(err instanceof ApiError ? err.message : "Couldn't sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 1000, display: "grid", gap: 40, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", alignItems: "center", minHeight: "100dvh" }}>
      <section>
        <h1>The Desk.</h1>
        <p style={{ fontSize: 18 }} className="muted">Where people check what the machines couldn&apos;t. Review cases, find people, approve follow-ups.</p>
        <p className="muted">Staff accounts only. Sessions last 30 minutes. This is a separate sign-in from the public site.</p>
      </section>
      <form className="panel pop" onSubmit={submit}>
        <h2>Sign in</h2>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label htmlFor="pw">Password</label>
        <input id="pw" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {needCode && (
          <>
            <label htmlFor="code">Authenticator code or recovery code</label>
            <input id="code" inputMode="numeric" autoComplete="one-time-code" autoFocus value={code} onChange={(e) => setCode(e.target.value)} required />
            <p className="muted">Open your authenticator app and enter the 6-digit code. If you lost it, enter one of your single-use recovery codes.</p>
          </>
        )}
        {error && <p className="err" role="alert">{error}</p>}
        <p><button disabled={busy} style={{ width: "100%", height: 48 }}>{busy ? "Please wait…" : "Sign in"}</button></p>
      </form>
    </main>
  );
}
