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

const initials = (n: string) => n.replace(/^(dr|prof|shri|smt)\.?\s+/i, "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => Array.from(w)[0]).join("").toUpperCase();

/** Review: the cases that need a person, as a deck. J/K move, Enter opens, T takes. The selected case is shown in focus beside the list. */
export default function QueuePage() {
  const router = useRouter();
  const [items, setItems] = useState<Item[] | null>(null);
  const [perms, setPerms] = useState<string[]>([]);
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [sel, setSel] = useState(0);

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

  async function reindex() {
    setError("");
    try {
      const r = await api<{ profiles_indexed: number; edges: number }>("/v1/admin/reindex", { method: "POST" });
      setError(`Reindexed ${r.profiles_indexed} profiles and ${r.edges} relationships.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reindex failed");
    }
  }

  // Keyboard triage: J / K move, Enter opens the case, T takes it. Typing in a field is never intercepted.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (!items?.length || e.metaKey || e.ctrlKey || e.altKey || (t && /^(input|textarea|select)$/i.test(t.tagName))) return;
      const at = Math.min(sel, items.length - 1);
      if (e.key === "j") setSel(Math.min(at + 1, items.length - 1));
      else if (e.key === "k") setSel(Math.max(at - 1, 0));
      else if (e.key === "Enter") router.push(`/case/${items[at].id}`);
      else if (e.key === "t" && perms.includes("review.claim")) void take(items[at].id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, sel, perms, router]);

  const overdue = (i: Item) => i.sla_due_at && new Date(i.sla_due_at) < new Date();
  const held = (i: Item) => Boolean(i.assigned_to && i.locked_until && new Date(i.locked_until) > new Date());
  const cur = items && items.length ? items[Math.min(sel, items.length - 1)] : null;

  return (
    <main>
      <div className="row">
        <h1 className="grow">Review</h1>
        <button className="secondary" onClick={reindex}>Reindex search</button>
      </div>
      <p className="muted"><kbd>J</kbd> <kbd>K</kbd> move · <kbd>Enter</kbd> open · <kbd>T</kbd> take · <kbd>Ctrl K</kbd> go anywhere</p>
      {error && <p className="err" role="alert">{error}</p>}

      {ov && (
        <div className="pulse" role="status" aria-label="Queue overview">
          <div><b>{ov.queue.open}</b><span>waiting for a person</span></div>
          <div><b className={ov.queue.overdue > 0 ? "hot" : ""}>{ov.queue.overdue}</b><span>overdue{ov.queue.overdue > 0 ? " (needs attention)" : ""}</span></div>
          <div><b>{ov.queue.oldest_hours ?? 0}<small style={{ fontSize: 22 }}> h</small></b><span>oldest waiting</span></div>
          {ov.approvals && <div><b className={ov.approvals.pending > 0 ? "hot" : ""}>{ov.approvals.pending}</b><span>approvals waiting</span></div>}
        </div>
      )}
      {ov && Object.keys(ov.queue.by_reason_code).length > 0 && (
        <p>{Object.entries(ov.queue.by_reason_code).sort((a, b) => b[1] - a[1]).map(([c, n]) => <span className="chip" key={c}>{c} {n}</span>)}</p>
      )}

      {items === null ? <p className="muted">Loading…</p> : items.length === 0 ? (
        <div className="empty"><h2>All clear.</h2><p>Nothing is waiting for a person right now.</p></div>
      ) : (
        <div className="deck">
          <ul className="cases" aria-label="Cases">
            {items.map((i, n) => (
              <li key={i.id}>
                <button type="button" className="case" aria-selected={n === sel} onClick={() => setSel(n)} onDoubleClick={() => router.push(`/case/${i.id}`)}>
                  <span className="av" aria-hidden>{initials(i.profile?.full_name ?? "?")}</span>
                  <span style={{ minWidth: 0, flex: 1 }}>
                    <b>{i.profile?.full_name ?? "(removed)"}</b>
                    <span className="muted">{[i.profile?.sector, i.profile?.state].filter(Boolean).join(" · ")}</span>
                    <span style={{ display: "block", marginTop: 4 }}>{(i.details.reason_codes ?? []).map((c) => <span className="chip" key={c}>{c}</span>)}</span>
                  </span>
                  {overdue(i) && <span className="chip" style={{ background: "var(--seal-tint)", color: "var(--seal)" }}>overdue</span>}
                </button>
              </li>
            ))}
          </ul>

          {cur && (
            <aside className="panel pop focus" aria-label="Selected case">
              <h2>{cur.profile?.full_name ?? "(removed)"}</h2>
              <p className="muted">{[cur.profile?.sector, cur.profile?.state].filter(Boolean).join(" · ")}</p>
              <dl>
                <div><dt>Why it is here</dt><dd>{cur.reason}</dd></div>
                <div><dt>Reason codes</dt><dd>{(cur.details.reason_codes ?? []).map((c) => <span className="chip" key={c}>{c}</span>) || "none"}</dd></div>
                <div><dt>Due</dt><dd className={overdue(cur) ? "warn" : ""}>{cur.sla_due_at ? new Date(cur.sla_due_at).toLocaleString() : "no deadline"}{overdue(cur) ? " (overdue)" : ""}</dd></div>
                <div><dt>Status</dt><dd>{held(cur) ? "Being reviewed by someone" : "Open"}</dd></div>
              </dl>
              <div className="row" style={{ marginTop: 18 }}>
                <Link href={`/case/${cur.id}`}><button type="button">Open case</button></Link>
                {!held(cur) && perms.includes("review.claim") && <button type="button" className="secondary" onClick={() => take(cur.id)}>Take it</button>}
                {!perms.includes("review.claim") && <span className="muted">View only</span>}
              </div>
            </aside>
          )}
        </div>
      )}
      <p className="muted" style={{ marginTop: 28 }}>Your permissions: {perms.length ? perms.join(", ") : "none"}</p>
    </main>
  );
}
