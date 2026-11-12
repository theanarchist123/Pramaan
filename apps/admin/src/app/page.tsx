"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

interface Item {
  id: string; profile_id: string; reason: string; created_at: string; sla_due_at: string | null;
  assigned_to: string | null; locked_until: string | null;
  details: { reason_codes?: string[] };
  profile: { full_name: string; sector: string; state: string } | null;
}

interface Overview {
  queue: { open: number; unassigned: number; held: number; overdue: number; oldest_hours: number | null; by_reason_code: Record<string, number> };
  approvals?: { pending: number; oldest_hours: number | null };
  registry?: { profiles: Record<string, number>; certificates: number; revoked: number };
  agents?: { calls_24h: number; failed_24h: number };
}

function Tile({ label, value, note, warn }: { label: string; value: string | number; note?: string; warn?: boolean }) {
  return (
    <div className="tile">
      <div className="muted">{label}</div>
      <div className={`tile-n${warn ? " warn" : ""}`}>{value}{warn ? <span className="sr-only"> (needs attention)</span> : null}</div>
      {note && <div className="muted">{note}</div>}
    </div>
  );
}

export default function QueuePage() {
  const router = useRouter();
  const [items, setItems] = useState<Item[] | null>(null);
  const [perms, setPerms] = useState<string[]>([]);
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [me, q, o] = await Promise.all([
        api<{ permissions: string[] }>("/v1/admin/me/permissions"),
        api<Item[]>("/v1/admin/review"),
        api<Overview>("/v1/admin/overview"),
      ]);
      setPerms(me.permissions);
      setItems(q);
      setOv(o);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else if (e instanceof ApiError && e.code === "mfa_required") router.push("/security");
      else setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [router]);
  useEffect(() => { void load(); }, [load]);

  async function take(id: string) {
    try {
      await api(`/v1/admin/review/${id}/claim`, { method: "POST" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't take the case");
    }
  }

  async function signOut() {
    await api("/v1/admin/auth/logout", { method: "POST" }).catch(() => {});
    router.push("/login");
  }

  const overdue = (i: Item) => i.sla_due_at && new Date(i.sla_due_at) < new Date();

  return (
    <main>
      <div className="row">
        <h1 className="grow">Review queue</h1>
        {perms.includes("agent_run.read") && <Link href="/calibration">Calibration</Link>}
        <Link href="/images">Photographs</Link>
        {perms.includes("profile.suspend") && <Link href="/registry">Registry</Link>}
        <Link href="/security">Security</Link>
        <button className="secondary" onClick={signOut}>Sign out</button>
      </div>
      {error && <p className="err" role="alert">{error}</p>}
      {ov && (
        <section aria-label="Overview" className="tiles">
          <Tile label="Open cases" value={ov.queue.open} note={`${ov.queue.unassigned} unassigned, ${ov.queue.held} being reviewed`} />
          <Tile label="Overdue" value={ov.queue.overdue} warn={ov.queue.overdue > 0} note={ov.queue.oldest_hours != null ? `oldest waiting ${ov.queue.oldest_hours} h` : "nothing waiting"} />
          {ov.approvals && <Tile label="Approvals waiting" value={ov.approvals.pending} warn={ov.approvals.pending > 0} note={ov.approvals.oldest_hours != null ? `oldest ${ov.approvals.oldest_hours} h` : undefined} />}
          {ov.registry && <Tile label="Approved profiles" value={ov.registry.profiles.approved ?? 0} note={`${ov.registry.certificates} certificates, ${ov.registry.revoked} revoked`} />}
          {ov.agents && <Tile label="Model calls, 24 h" value={ov.agents.calls_24h} note={`${ov.agents.failed_24h} failed`} warn={ov.agents.failed_24h > 0} />}
        </section>
      )}
      {ov && Object.keys(ov.queue.by_reason_code).length > 0 && (
        <p>{Object.entries(ov.queue.by_reason_code).sort((a, b) => b[1] - a[1]).map(([c, n]) => <span className="chip" key={c}>{c} {n}</span>)}</p>
      )}
      <div className="panel">
        {items === null ? <p className="muted">Loading...</p> : items.length === 0 ? <p className="muted">Nothing is waiting for a person.</p> : (
          <table>
            <thead><tr><th>Person</th><th>Why it is here</th><th>Due</th><th>Case</th></tr></thead>
            <tbody>
              {items.map((i) => {
                const held = i.assigned_to && i.locked_until && new Date(i.locked_until) > new Date();
                return (
                  <tr key={i.id}>
                    <td><Link href={`/case/${i.id}`}>{i.profile?.full_name ?? "(removed)"}</Link><div className="muted">{[i.profile?.sector, i.profile?.state].filter(Boolean).join(" · ")}</div></td>
                    <td>{(i.details.reason_codes ?? []).map((c) => <span className="chip" key={c}>{c}</span>)}<div className="muted">{i.reason}</div></td>
                    <td className={overdue(i) ? "warn" : "muted"}>{i.sla_due_at ? new Date(i.sla_due_at).toLocaleString() : ""}{overdue(i) ? " (overdue)" : ""}</td>
                    <td>{held ? <span className="muted">Being reviewed</span> : perms.includes("review.claim") ? <button className="secondary" onClick={() => take(i.id)}>Take case</button> : <span className="muted">View only</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <p className="muted">Your permissions: {perms.length ? perms.join(", ") : "none"}</p>
    </main>
  );
}
