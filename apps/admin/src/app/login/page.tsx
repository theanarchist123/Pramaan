"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await api<{ mfa_enrolled: boolean }>("/v1/admin/auth/login", { method: "POST", json: { email, password } });
      router.push(r.mfa_enrolled ? "/" : "/security");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 420 }}>
      <h1>Pramaan staff console</h1>
      <form className="panel" onSubmit={submit}>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label htmlFor="pw">Password</label>
        <input id="pw" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="err" role="alert">{error}</p>}
        <p><button disabled={busy}>Sign in</button></p>
        <p className="muted">Staff accounts only. Sessions last 30 minutes. This is a separate sign-in from the public site.</p>
      </form>
    </main>
  );
}
