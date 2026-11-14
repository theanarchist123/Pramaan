"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Icon, PageHead, Pill } from "@/components/ui";

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
      <PageHead
        eyebrow="Messages"
        title="Follow-ups"
        lead="The assistant finds people who need a nudge and drafts the message. You approve each one."
        actions={<button onClick={suggest} disabled={busy === "suggest"}>{busy === "suggest" ? "Drafting…" : "Draft nudges"}</button>}
      />
      {note && <p className="notice" role="status"><Icon name="mail" size={18} /><span>{note}</span></p>}
      <div className="seg" role="tablist" aria-label="Message status" style={{ margin: "14px 0 18px" }}>
        {FILTERS.map((f) => <button key={f} role="tab" aria-selected={filter === f} onClick={() => setFilter(f)}>{f} {count(f)}</button>)}
      </div>
      {msgs === null && <p className="muted">Loading…</p>}
      {msgs && shown.length === 0 && <div className="empty"><span className="art"><Icon name="inbox" size={28} /></span><h2>No {filter} messages.</h2><p>{filter === "draft" ? "Use “Draft nudges” to find people who could use a reminder." : "Nothing here yet."}</p></div>}
      {shown.map((m) => (
        <article key={m.id} className="panel">
          <div className="msg-head">
            <Pill tone="info" icon="mail">{KIND[m.kind] ?? m.kind}</Pill>
            <span className="muted">to {m.to_email}</span>
          </div>
          <p style={{ fontWeight: 700, fontSize: 16, margin: "0 0 8px" }}>{m.subject}</p>
          <pre className="msg-body muted">{m.body}</pre>
          {m.error && <p className="alert"><Icon name="alert" size={18} /><span>{m.error}</span></p>}
          {(m.status === "draft" || m.status === "scheduled") && (
            <div className="row" style={{ marginTop: 14 }}>
              <button disabled={busy === m.id} onClick={() => act(m, "send")}>Send now</button>
              <button className="secondary" disabled={busy === m.id} onClick={() => act(m, "schedule")}>Schedule in 1 hour</button>
              <button className="ghost" disabled={busy === m.id} onClick={() => act(m, "discard")}>Discard</button>
            </div>
          )}
        </article>
      ))}
    </main>
  );
}
