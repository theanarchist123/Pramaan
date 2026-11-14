"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

interface ConsentRow { kind: string; granted: boolean; text: string; created_at: string }
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Registry and compliance: see what a person agreed to (read only), and suspend or restore a public profile with a written reason. Both are audited. */
export default function RegistryPage() {
  const router = useRouter();
  const [pid, setPid] = useState("");
  const [consents, setConsents] = useState<ConsentRow[] | null>(null);
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const valid = UUID.test(pid.trim());

  function fail(e: unknown) {
    if (e instanceof ApiError && e.status === 401) router.push("/login");
    else setError(e instanceof Error ? e.message : "Something went wrong");
  }

  async function lookup() {
    setError(""); setMsg(""); setConsents(null);
    try { setConsents(await api<ConsentRow[]>(`/v1/admin/consents?profile_id=${pid.trim()}`)); } catch (e) { fail(e); }
  }

  async function change(action: "suspend" | "restore") {
    setError(""); setMsg(""); setBusy(true);
    try {
      await api(`/v1/admin/registry/profiles/${pid.trim()}/${action}`, { method: "POST", json: { reason: reason.trim() } });
      setMsg(action === "suspend" ? "Suspended. The profile is no longer public." : "Restored. The profile is public again.");
      setReason("");
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  return (
    <main>
      <div className="row"><h1 className="grow">Registry and compliance</h1></div>
      {error && <p className="err" role="alert">{error}</p>}
      {msg && <p className="panel" role="status">{msg}</p>}
      <section className="panel" aria-label="Find a profile">
        <label htmlFor="pid"><strong>Profile ID</strong></label>
        <input id="pid" value={pid} onChange={(e) => setPid(e.target.value)} placeholder="Paste a profile ID" autoComplete="off" />
        <div className="row"><button onClick={lookup} disabled={!valid}>Show consents</button></div>
        {pid && !valid && <p className="muted">That doesn&apos;t look like a profile ID.</p>}
      </section>
      {consents && (
        <section className="panel" aria-label="Consents">
          <strong>What this person agreed to</strong>
          {consents.length === 0 ? <p className="muted">No consent records.</p> : (
            <table>
              <thead><tr><th>Kind</th><th>Granted</th><th>Wording they saw</th><th>When</th></tr></thead>
              <tbody>{consents.map((c, i) => (
                <tr key={i}><td><span className="chip">{c.kind}</span></td><td>{c.granted ? "Yes" : "No"}</td><td>{c.text}</td><td>{new Date(c.created_at).toLocaleString()}</td></tr>
              ))}</tbody>
            </table>
          )}
          <p className="muted">Consent is changed by the person, never by staff.</p>
        </section>
      )}
      <section className="panel" aria-label="Suspend or restore">
        <strong>Suspend or restore</strong>
        <p className="muted">Suspending hides the profile everywhere public until someone restores it. You cannot do this to your own profile. Say why, in at least 10 characters.</p>
        <label htmlFor="reason">Reason</label>
        <textarea id="reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={500} />
        <div className="row">
          <button className="secondary" onClick={() => change("suspend")} disabled={!valid || reason.trim().length < 10 || busy}>Suspend</button>
          <button className="secondary" onClick={() => change("restore")} disabled={!valid || reason.trim().length < 10 || busy}>Restore</button>
        </div>
      </section>
    </main>
  );
}
