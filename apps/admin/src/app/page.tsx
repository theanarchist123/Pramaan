"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Avatar, Icon, PageHead, Pill, Stat } from "@/components/ui";
import { dueState, greeting, reasonLabel, tileFor } from "@/lib/labels";

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


/** Review: the cases that need a person, as a deck. J/K move, Enter opens, T takes. The selected case is shown in focus beside the list. */
export default function QueuePage() {
  const router = useRouter();
  const [items, setItems] = useState<Item[] | null>(null);
  const [perms, setPerms] = useState<string[]>([]);
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [sel, setSel] = useState(0);
  const [only, setOnly] = useState<string | null>(null);
  // The greeting and date depend on the viewer's clock and locale, so they are set after the page loads (the server cannot know them).
  const [today, setToday] = useState("");
  useEffect(() => setToday(`${greeting()} · ${new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}`), []);

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

  async function testEmail() {
    setError("");
    try {
      const r = await api<{ ok: boolean; provider: string; sent_to: string; reason: string; detail: string }>("/v1/admin/email/test", { method: "POST" });
      const why: Record<string, string> = {
        not_configured: "No email service is set up on the server.",
        network_blocked: "The server cannot reach the mail service (free hosts such as Render block SMTP: use BREVO_API_KEY).",
        auth_failed: "The mail service refused the login or API key.",
        sender_not_verified: "The sender address is not verified with the mail service.",
        recipient_refused: "The receiving server refused the address.",
      };
      setError(r.ok ? `Test email sent to ${r.sent_to} using ${r.provider}. Check your inbox (and spam).` : `Test email failed (${r.provider}): ${why[r.reason] ?? "unknown problem"} ${r.detail}`.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Test email failed");
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

  // Keyboard triage: J / K move, Enter opens the case, T takes it. Typing in a field is never intercepted. Works on the filtered list you can see.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const shown = (items ?? []).filter((i) => !only || (i.details.reason_codes ?? []).includes(only));
      if (!shown.length || e.metaKey || e.ctrlKey || e.altKey || (t && /^(input|textarea|select)$/i.test(t.tagName))) return;
      const at = Math.min(sel, shown.length - 1);
      if (e.key === "j") setSel(Math.min(at + 1, shown.length - 1));
      else if (e.key === "k") setSel(Math.max(at - 1, 0));
      else if (e.key === "Enter") router.push(`/case/${shown[at].id}`);
      else if (e.key === "t" && perms.includes("review.claim")) void take(shown[at].id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, only, sel, perms, router]);

  const visible = (items ?? []).filter((i) => !only || (i.details.reason_codes ?? []).includes(only));
  const overdue = (i: Item) => i.sla_due_at && new Date(i.sla_due_at) < new Date();
  const held = (i: Item) => Boolean(i.assigned_to && i.locked_until && new Date(i.locked_until) > new Date());

  const list = visible;
  const cur = list.length ? list[Math.min(sel, list.length - 1)] : null;
  const codes = ov ? Object.entries(ov.queue.by_reason_code).sort((a, b) => b[1] - a[1]) : [];

  return (
    <main>
      <PageHead
        eyebrow={today || undefined}
        title="Review"
        lead={ov ? (ov.queue.open === 0 ? "Nothing is waiting for a person right now." : `${ov.queue.open} ${ov.queue.open === 1 ? "case needs" : "cases need"} a person to look at the evidence.`) : "Cases that need a person to look at the evidence."}
        actions={<><button className="secondary" onClick={testEmail}>Send test email</button> <button className="secondary" onClick={reindex}>Reindex search</button></>}
      />
      {error && <p className="alert" role="alert"><Icon name="alert" size={18} /><span>{error}</span></p>}

      {ov && (
        <div className="stats" role="status" aria-label="Queue overview">
          <Stat n={ov.queue.open} label="waiting for a person" icon="inbox" tone={ov.queue.open > 0 ? "info" : "ok"} />
          <Stat n={ov.queue.overdue} label={ov.queue.overdue > 0 ? "overdue (needs attention)" : "overdue"} icon="alert" tone={ov.queue.overdue > 0 ? "bad" : "ok"} />
          <Stat n={ov.queue.oldest_hours ?? 0} unit=" h" label="oldest waiting" icon="clock" tone={(ov.queue.oldest_hours ?? 0) > 24 ? "warn" : "quiet"} />
          {ov.approvals && <Stat n={ov.approvals.pending} label="approvals waiting" icon="shield" tone={ov.approvals.pending > 0 ? "warn" : "ok"} />}
        </div>
      )}

      {codes.length > 0 && (
        <div className="row" role="group" aria-label="Filter by reason" style={{ marginBottom: 6 }}>
          <button type="button" className="filter" aria-pressed={only === null} onClick={() => { setOnly(null); setSel(0); }}>All</button>
          {codes.map(([c, n]) => (
            <button type="button" className="filter" key={c} aria-pressed={only === c} onClick={() => { setOnly(only === c ? null : c); setSel(0); }}>{reasonLabel(c)} {n}</button>
          ))}
        </div>
      )}

      {items === null ? <p className="muted">Loading…</p> : list.length === 0 ? (
        <div className="empty">
          <span className="art"><Icon name="check" size={30} /></span>
          <h2>All clear.</h2>
          <p>{only ? "Nothing matches that filter." : "Nothing is waiting for a person right now."}</p>
        </div>
      ) : (
        <div className="deck">
          <ul className="cases" aria-label="Cases">
            {list.map((i, n) => {
              const due = dueState(i.sla_due_at);
              const name = i.profile?.full_name ?? "(removed)";
              return (
                <li key={i.id}>
                  <button type="button" className="case" aria-selected={n === Math.min(sel, list.length - 1)} onClick={() => setSel(n)} onDoubleClick={() => router.push(`/case/${i.id}`)}>
                    <Avatar name={name} tile={tileFor(i.profile?.sector ?? name)} />
                    <span style={{ minWidth: 0, flex: 1 }}>
                      <b>{name}</b>
                      <span className="muted">{[i.profile?.sector, i.profile?.state].filter(Boolean).join(" · ")}</span>
                      <span className="meta">
                        {(i.details.reason_codes ?? []).map((c) => <span className="chip" key={c}>{reasonLabel(c)}</span>)}
                      </span>
                    </span>
                    <span style={{ display: "grid", gap: 6, justifyItems: "end" }}>
                      <Pill tone={due.tone}>{due.late ? "overdue" : due.text}</Pill>
                      {held(i) && <Pill tone="info" icon="user">In review</Pill>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          {cur && (() => {
            const due = dueState(cur.sla_due_at);
            const name = cur.profile?.full_name ?? "(removed)";
            return (
              <aside className="panel pop focus" aria-label="Selected case">
                <div className="row" style={{ marginBottom: 10 }}>
                  <Avatar name={name} tile={tileFor(cur.profile?.sector ?? name)} size={56} />
                  <div className="grow">
                    <h2>{name}</h2>
                    <p className="muted" style={{ margin: 0 }}>{[cur.profile?.sector, cur.profile?.state].filter(Boolean).join(" · ")}</p>
                  </div>
                </div>
                <dl>
                  <div><dt>Why it is here</dt><dd>{cur.reason}</dd></div>
                  <div><dt>Reason codes</dt><dd>{(cur.details.reason_codes ?? []).map((c) => <span className="chip" key={c}>{c}</span>)}</dd></div>
                  <div>
                    <dt>Due</dt>
                    <dd className={overdue(cur) ? "warn" : ""}>
                      {cur.sla_due_at ? new Date(cur.sla_due_at).toLocaleString() : "no deadline"}{overdue(cur) ? " (overdue)" : ""}
                      {" "}<Pill tone={due.tone}>{due.text}</Pill>
                    </dd>
                  </div>
                  <div><dt>Status</dt><dd>{held(cur) ? "Being reviewed by someone" : "Open"}</dd></div>
                </dl>
                <div className="row" style={{ marginTop: 20 }}>
                  <Link href={`/case/${cur.id}`}><button type="button">Open case <Icon name="arrow" size={16} /></button></Link>
                  {!held(cur) && perms.includes("review.claim") && <button type="button" className="secondary" onClick={() => take(cur.id)}>Take it</button>}
                  {!perms.includes("review.claim") && <span className="muted">View only</span>}
                </div>
              </aside>
            );
          })()}
        </div>
      )}

      {list.length > 0 && (
        <div className="hintbar" aria-hidden="true">
          <span><kbd>J</kbd><kbd>K</kbd> move</span><span><kbd>Enter</kbd> open</span><span><kbd>T</kbd> take</span><span><kbd>Ctrl K</kbd> go anywhere</span>
        </div>
      )}
      <p className="muted" style={{ marginTop: 28, fontSize: 13 }}>Your permissions: {perms.length ? perms.join(", ") : "none"}</p>
    </main>
  );
}
