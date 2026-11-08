"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock, Mail, Send, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { AdminNav } from "@/components/admin/admin-nav";
import { AgentAvatar } from "@/components/agent-feed";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface Msg {
  id: string; kind: string; to_email: string; subject: string; body: string; status: string; error: string;
  scheduled_for: string | null; sent_at: string | null; created_at: string;
}

const KIND: Record<string, string> = {
  welcome_share: "Congratulations & share",
  needs_document: "Needs a document",
  finish_profile: "Finish your profile",
};
const FILTERS = ["draft", "scheduled", "sent", "discarded"] as const;

export default function OutreachPage() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const [msgs, setMsgs] = useState<Msg[] | null>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("draft");
  const [busy, setBusy] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, { subject: string; body: string }>>({});

  const load = useCallback(() => api<Msg[]>("/v1/admin/outbox").then(setMsgs).catch(() => setMsgs([])), []);
  useEffect(() => {
    if (ready && !user) router.replace("/auth?next=/admin/outreach");
    else if (ready && user?.role === "admin") load();
  }, [ready, user, router, load]);

  async function suggest() {
    setBusy("suggest");
    try {
      const created = await api<Msg[]>("/v1/admin/outreach/suggest", { method: "POST", json: {} });
      toast.success(created.length ? `Doot drafted ${created.length} message(s) for your approval` : "Everyone who needs a nudge already has a draft");
      setFilter("draft");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't draft");
    } finally { setBusy(null); }
  }

  async function act(m: Msg, action: "send" | "discard" | "schedule", json?: unknown) {
    setBusy(m.id);
    try {
      const e = edits[m.id];
      if (e && action !== "discard") await api(`/v1/admin/outbox/${m.id}`, { method: "PATCH", json: e });
      const r = await api<Msg>(`/v1/admin/outbox/${m.id}/${action}`, { method: "POST", json });
      if (action === "send") {
        if (r.status === "sent") toast.success(r.error.startsWith("dry-run") ? "Recorded as sent (dry run — SMTP isn't configured)" : "Sent");
        else toast.error(r.error || "Not sent");
      }
      if (action === "schedule") toast.success("Scheduled");
      setEdits((prev) => {
        const next = { ...prev };
        delete next[m.id];
        return next;
      });
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    } finally { setBusy(null); }
  }

  if (!ready) return <div className="mx-auto max-w-5xl px-4 py-12"><Skeleton className="h-64 rounded-2xl" /></div>;
  if (user && user.role !== "admin") return <p className="p-16 text-center text-muted-foreground">Administrators only.</p>;

  const shown = (msgs ?? []).filter((m) => m.status === filter);
  const count = (s: string) => (msgs ?? []).filter((m) => m.status === s).length;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="flex items-center gap-3 text-4xl font-semibold"><AgentAvatar name="Doot" className="size-10 text-sm" /> Outreach</h1>
      <p className="mt-1 mb-6 max-w-2xl text-muted-foreground">
        Doot finds people who need a nudge and drafts the message. <b>Nothing is ever sent without you:</b> edit, then send now or schedule.
      </p>
      <AdminNav />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" className="flex gap-1">
          {FILTERS.map((f) => (
            <button key={f} role="tab" aria-selected={filter === f} onClick={() => setFilter(f)}
              className={cn("rounded-lg px-3 py-1.5 text-sm capitalize transition-colors", filter === f ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted")}>
              {f} <span className="tabular-nums opacity-60">{count(f)}</span>
            </button>
          ))}
        </div>
        <Button onClick={suggest} disabled={busy === "suggest"}><Sparkles /> Ask Doot for drafts</Button>
      </div>

      <ul className="mt-5 space-y-4">
        {msgs === null ? <Skeleton className="h-40 rounded-2xl" /> : shown.length === 0 && (
          <li className="rounded-2xl border border-dashed border-border p-12 text-center text-muted-foreground">
            <Mail className="mx-auto mb-2 size-8 opacity-40" />
            No {filter} messages.{filter === "draft" && " Press “Ask Doot for drafts”."}
          </li>
        )}
        {shown.map((m) => {
          const e = edits[m.id] ?? { subject: m.subject, body: m.body };
          const editable = m.status === "draft" || m.status === "scheduled";
          return (
            <li key={m.id} className="rounded-2xl border border-border bg-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span className="rounded-full bg-indigo-soft px-2 py-0.5 font-medium text-indigo">{KIND[m.kind] ?? m.kind}</span>
                <span>To <b className="text-foreground">{m.to_email}</b></span>
              </div>
              {editable ? (
                <>
                  <Input className="mt-3 h-10 font-medium" aria-label="Subject" value={e.subject} onChange={(ev) => setEdits({ ...edits, [m.id]: { ...e, subject: ev.target.value } })} />
                  <Textarea className="mt-2 font-sans text-sm" rows={10} aria-label="Message" value={e.body} onChange={(ev) => setEdits({ ...edits, [m.id]: { ...e, body: ev.target.value } })} />
                </>
              ) : (
                <>
                  <p className="mt-3 font-medium">{m.subject}</p>
                  <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-muted-foreground">{m.body}</pre>
                </>
              )}
              {m.error && <p className={cn("mt-2 text-xs", m.status === "sent" ? "text-muted-foreground" : "text-destructive")}>{m.error}</p>}
              {m.status === "scheduled" && m.scheduled_for && <p className="mt-2 text-xs text-muted-foreground">Will send {new Date(m.scheduled_for).toLocaleString()}</p>}
              {m.sent_at && <p className="mt-2 text-xs text-muted-foreground">Sent {new Date(m.sent_at).toLocaleString()}</p>}
              {editable && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button disabled={busy === m.id} onClick={() => act(m, "send")}><Send /> Send now</Button>
                  <Button variant="outline" disabled={busy === m.id} onClick={() => act(m, "schedule", { at: new Date(Date.now() + 3600_000).toISOString() })}><CalendarClock /> Schedule in 1 hour</Button>
                  <Button variant="ghost" disabled={busy === m.id} onClick={() => act(m, "discard")}><Trash2 /> Discard</Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
