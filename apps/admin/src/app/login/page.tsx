"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Icon } from "@/components/ui";

/** Staff sign-in: password first, then the authenticator code (or a recovery code) once the server asks for it. */
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [code, setCode] = useState("");
  const [needCode, setNeedCode] = useState(false);
  const [recovery, setRecovery] = useState(false);
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
    <div className="auth">
      <aside className="auth-brand">
        <span className="mark"><i><svg viewBox="0 0 40 40" width="20" height="20" aria-hidden="true"><path d="M8 21l8 8L33 11" fill="none" stroke="#FFB81C" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" /></svg></i>Pramaan Desk</span>
        <div>
          <h1>Where people check what machines couldn&apos;t.</h1>
          <p>Review cases, find people, approve follow-ups. Every decision is yours, and every one is recorded.</p>
        </div>
        <div className="auth-deck" aria-hidden="true">
          <div><span className="tick"><Icon name="check" size={16} /></span><span>Document matches the name<small>Auto-checked, ready to approve</small></span></div>
          <div><span className="tick hold"><Icon name="clock" size={16} /></span><span>Waiting for a person<small>Due in 5 h</small></span></div>
          <div><span className="tick flag"><Icon name="flag" size={16} /></span><span>Name does not match<small>Needs a closer look</small></span></div>
        </div>
        <ul>
          <li><Icon name="shield" size={18} />Authenticator code on every sign-in</li>
          <li><Icon name="clock" size={18} />Sessions end after 30 minutes</li>
          <li><Icon name="key" size={18} />Separate from the public site&apos;s accounts</li>
        </ul>
      </aside>

      <main className="auth-form">
        <form className="auth-card" onSubmit={submit}>
          <h2>Sign in</h2>
          <p className="muted" style={{ margin: 0 }}>Staff accounts only.</p>
          <div className="steps" aria-hidden="true"><span className="on" /><span className={needCode ? "on" : ""} /></div>
          <p className="muted" style={{ margin: "0 0 4px", fontSize: 13 }}>{needCode ? "Step 2 of 2: your authenticator" : "Step 1 of 2: your account"}</p>

          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required readOnly={needCode} />
          <label htmlFor="pw">Password</label>
          <div className="field">
            <input id="pw" type={show ? "text" : "password"} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required readOnly={needCode} style={{ paddingRight: 48 }} />
            <button type="button" className="reveal" onClick={() => setShow((v) => !v)} aria-label={show ? "Hide characters" : "Show characters"}><Icon name={show ? "eyeoff" : "eye"} size={18} /></button>
          </div>

          {needCode && (
            <>
              <label htmlFor="code">Authenticator code or recovery code</label>
              <input
                id="code" className={recovery ? undefined : "otp"} inputMode={recovery ? "text" : "numeric"} autoComplete="one-time-code" autoFocus
                maxLength={recovery ? 9 : 6} placeholder={recovery ? "abcd-efgh" : "000000"} value={code}
                onChange={(e) => setCode(recovery ? e.target.value : e.target.value.replace(/\D/g, ""))} required
              />
              <p className="fine" style={{ marginTop: 8 }}>
                {recovery ? "Enter one of your single-use recovery codes." : "Open your authenticator app and enter the 6-digit code."}{" "}
                <button type="button" className="ghost" style={{ height: "auto", padding: "0 4px", textDecoration: "underline" }} onClick={() => { setRecovery((v) => !v); setCode(""); }}>
                  {recovery ? "Use the app instead" : "Lost your phone? Use a recovery code"}
                </button>
              </p>
            </>
          )}

          {error && <p className="alert" role="alert"><Icon name="alert" size={18} /><span>{error}</span></p>}
          <p style={{ margin: "20px 0 0" }}>
            <button disabled={busy} style={{ width: "100%", height: 50, fontSize: 16 }}>{busy ? "Please wait…" : "Sign in"}</button>
          </p>
          <p className="fine">Not a staff member? This page is not for you. Members sign in on the public site.</p>
        </form>
      </main>
    </div>
  );
}
