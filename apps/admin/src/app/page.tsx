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

export default function QueuePage() {
  const router = useRouter();
  const [items, setItems] = useState<Item[] | null>(null);
  const [perms, setPerms] = useState<string[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [me, q] = await Promise.all([
        api<{ permissions: string[] }>("/v1/admin/me/permissions"),
        api<Item[]>("/v1/admin/review"),
      ]);
      setPerms(me.permissions);
      setItems(q);
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
        <Link href="/security">Security</Link>
        <button className="secondary" onClick={signOut}>Sign out</button>
      </div>
      {error && <p className="err" role="alert">{error}</p>}
      <div className="panel">
        {items === null ? <p className="muted">Loading...</p> : items.length === 0 ? <p className="muted">Nothing is waiting for a person.</p> : (
          <table>
            <thead><tr><th>Person</th><th>Why it is here</th><th>Due</th><th>Case</th></tr></thead>
            <tbody>
              {items.map((i) => {
                const held = i.assigned_to && i.locked_until && new Date(i.locked_until) > new Date();
                return (
                  <tr key={i.id}>
                    <td>{i.profile?.full_name ?? "(removed)"}<div className="muted">{[i.profile?.sector, i.profile?.state].filter(Boolean).join(" · ")}</div></td>
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
