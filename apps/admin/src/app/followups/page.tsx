"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

interface Msg {
  id: string; kind: string; to_email: string; subject: string; body: string; status: string; error: string;
  scheduled_for: string | null; sent_at: string | null;
}
const KIND: Record<string, string> = { welcome_share: "Congratulations and share", needs_document: "Needs a document", finish_profile: "Finish your profile", invite: "Invitation" };
const FILTERS = ["draft", "scheduled", "sent", "discarded"] as const;

/** Follow-ups: messages the assistant drafted. A person approves every one; nothing is sent from here without a click. */
export default function FollowupsPage() {
  const router = useRouter();
  const [msgs, setMsgs] = useState<Msg[] | null>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("draft");
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    try {
      setMsgs(await api<Msg[]>("/v1/admin/outbox"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setNote(e instanceof Error ? e.message : "Failed to load");
      setMsgs([]);
    }
  }, [router]);
  useEffect(() => { void load(); }, [load]);

  async function suggest() {
    setBusy("suggest");
    try {
      const made = await api<Msg[]>("/v1/admin/outreach/suggest", { method: "POST", json: {} });
      setNote(made.length ? `Drafted ${made.length} message(s) for your approval.` : "Everyone who needs a nudge already has a draft.");
      setFilter("draft");
      await load();
    } catch (e) { setNote(e instanceof Error ? e.message : "Couldn't draft"); } finally { setBusy(""); }
  }
  async function act(m: Msg, action: "send" | "discard" | "schedule") {
    setBusy(m.id);
    try {
      await api(`/v1/admin/outbox/${m.id}/${action}`, { method: "POST", json: action === "schedule" ? { at: new Date(Date.now() + 3600_000).toISOString() } : undefined });
      await load();
    } catch (e) { setNote(e instanceof Error ? e.message : "Action failed"); } finally { setBusy(""); }
  }

  const shown = (msgs ?? []).filter((m) => m.status === filter);
  const count = (s: string) => (msgs ?? []).filter((m) => m.status === s).length;

  return (
    <main>
      <div className="row"><h1 className="grow">Follow-ups</h1><button onClick={suggest} disabled={busy === "suggest"}>Draft nudges</button></div>
      <p className="muted">The assistant finds people who need a nudge and drafts the message. You approve each one.</p>
      {note && <p role="status">{note}</p>}
      <div className="row" role="tablist">
        {FILTERS.map((f) => <button key={f} role="tab" aria-selected={filter === f} className={filter === f ? "" : "secondary"} onClick={() => setFilter(f)}>{f} {count(f)}</button>)}
      </div>
      <div style={{ height: 12 }} />
      {msgs === null && <p className="muted">Loading…</p>}
      {msgs && shown.length === 0 && <p className="panel muted">No {filter} messages.</p>}
      {shown.map((m) => (
        <article key={m.id} className="panel">
          <div className="muted"><span className="chip">{KIND[m.kind] ?? m.kind}</span> to {m.to_email}</div>
          <p style={{ fontWeight: 600 }}>{m.subject}</p>
          <pre style={{ whiteSpace: "pre-wrap", font: "inherit", margin: 0 }} className="muted">{m.body}</pre>
          {m.error && <p className="warn">{m.error}</p>}
          {(m.status === "draft" || m.status === "scheduled") && (
            <div className="row" style={{ marginTop: 10 }}>
              <button disabled={busy === m.id} onClick={() => act(m, "send")}>Send now</button>
              <button className="secondary" disabled={busy === m.id} onClick={() => act(m, "schedule")}>Schedule in 1 hour</button>
              <button className="secondary" disabled={busy === m.id} onClick={() => act(m, "discard")}>Discard</button>
            </div>
          )}
        </article>
      ))}
    </main>
  );
}
