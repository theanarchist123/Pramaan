"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, CircleCheck, CircleX, ExternalLink, FileCode2, Hammer, Loader2, Rocket, Sparkles, X } from "lucide-react";
import { toast } from "sonner";
import { AdminNav } from "@/components/admin/admin-nav";
import { AgentAvatar } from "@/components/agent-feed";
import { CodeBlock } from "@/components/developers/code";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError, API_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface Field { id: string; key: string; label: string; type: string; options: string[]; help_text: string; searchable: boolean; active: boolean; created_by: string }
interface Proposal { key: string; label: string; type: string; options: string[]; help_text: string; searchable: boolean; reasoning: string }
interface Step { name: string; ok: boolean; output: string }
interface Change {
  id: string; request: string; slug: string; summary: string; status: string; files: Record<string, string>;
  checks: { guard?: string[]; attempts?: number; history?: { step: string; output: string }[]; sandbox?: { ran: boolean; passed: boolean; reason?: string; steps: Step[]; seconds?: number } };
}

const STATUS: Record<string, { label: string; cls: string }> = {
  proposed: { label: "Working…", cls: "bg-muted text-muted-foreground" },
  rejected_by_guard: { label: "Blocked by the code guard", cls: "bg-destructive/10 text-destructive" },
  checks_failed: { label: "Checks failed", cls: "bg-destructive/10 text-destructive" },
  ready: { label: "Ready for your approval", cls: "bg-verified-soft text-verified" },
  applied: { label: "Live", cls: "bg-indigo-soft text-indigo" },
  rejected: { label: "Rejected", cls: "bg-muted text-muted-foreground" },
};

export default function BuilderPage() {
  const { user, ready } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (ready && !user) router.replace("/auth?mode=login&next=/admin/builder");
  }, [ready, user, router]);
  if (!ready) return <div className="mx-auto max-w-5xl px-4 py-12"><Skeleton className="h-64 rounded-2xl" /></div>;
  if (user && user.role !== "admin") return <p className="p-16 text-center text-muted-foreground">Administrators only.</p>;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="flex items-center gap-3 text-4xl font-semibold"><AgentAvatar name="Shilpkar" className="size-10 text-sm" /> Builder</h1>
      <p className="mt-1 mb-6 max-w-2xl text-muted-foreground">
        Describe what you need. Shilpkar adds new profile fields instantly — and for bigger ideas writes a small read-only plugin that must
        pass a code guard, an isolated sandbox and your approval before it goes live. No developer, no redeploy.
      </p>
      <AdminNav />
      <div className="space-y-12">
        <FieldsSection />
        <PluginsSection />
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ fields (no code)
function FieldsSection() {
  const [fields, setFields] = useState<Field[] | null>(null);
  const [request, setRequest] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<{ p: Proposal; errors: string[] } | null>(null);

  const load = useCallback(() => api<Field[]>("/v1/admin/fields").then(setFields).catch(() => setFields([])), []);
  useEffect(() => void load(), [load]);

  async function propose(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api<{ proposal: Proposal; errors: string[] }>("/v1/admin/builder/field-proposal", { method: "POST", json: { request } });
      setDraft({ p: r.proposal, errors: r.errors });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't draft the field");
    } finally { setBusy(false); }
  }

  async function approve() {
    if (!draft) return;
    try {
      await api("/v1/admin/fields", { method: "POST", json: { ...draft.p, created_by: "shilpkar" } });
      toast.success(`“${draft.p.label}” is live — forms, profiles, search and the interviewer already know about it`);
      setDraft(null);
      setRequest("");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't create the field");
    }
  }

  return (
    <section aria-labelledby="fields-h">
      <h2 id="fields-h" className="text-2xl font-semibold">Profile fields <span className="text-sm font-normal text-muted-foreground">· instant, no code</span></h2>
      <form onSubmit={propose} className="mt-4 flex gap-2">
        <Input value={request} onChange={(e) => setRequest(e.target.value)} placeholder="e.g. add a patents held field" className="h-11" aria-label="Describe the field you want" />
        <Button type="submit" className="h-11" disabled={busy || request.trim().length < 5}>{busy ? <Loader2 className="animate-spin" /> : <Sparkles />} Draft it</Button>
      </form>

      {draft && (
        <div className="mt-4 rounded-2xl border-2 border-primary/40 bg-card p-5">
          <p className="text-xs font-medium text-primary">Shilpkar proposes — nothing exists until you approve</p>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            <label className="text-sm">Label<Input className="mt-1" value={draft.p.label} onChange={(e) => setDraft({ ...draft, p: { ...draft.p, label: e.target.value } })} /></label>
            <label className="text-sm">Key<Input className="mt-1 font-mono" value={draft.p.key} onChange={(e) => setDraft({ ...draft, p: { ...draft.p, key: e.target.value } })} /></label>
            <label className="text-sm">Type
              <select className="mt-1 h-9 w-full rounded-lg border border-input bg-background px-2" value={draft.p.type} onChange={(e) => setDraft({ ...draft, p: { ...draft.p, type: e.target.value } })}>
                {["text", "number", "date", "select", "url", "list"].map((t) => <option key={t}>{t}</option>)}
              </select>
            </label>
            <label className="text-sm">Hint shown to the person<Input className="mt-1" value={draft.p.help_text} onChange={(e) => setDraft({ ...draft, p: { ...draft.p, help_text: e.target.value } })} /></label>
            {draft.p.type === "select" && (
              <label className="text-sm sm:col-span-2">Options (comma separated)
                <Input className="mt-1" value={draft.p.options.join(", ")} onChange={(e) => setDraft({ ...draft, p: { ...draft.p, options: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) } })} />
              </label>
            )}
          </div>
          <label className="mt-3 flex items-center gap-2 text-sm"><Switch checked={draft.p.searchable} onCheckedChange={(v) => setDraft({ ...draft, p: { ...draft.p, searchable: v } })} /> Include in search</label>
          <p className="mt-2 text-xs text-muted-foreground">{draft.p.reasoning}</p>
          {draft.errors.length > 0 && <ul className="mt-2 list-disc pl-5 text-sm text-destructive">{draft.errors.map((e) => <li key={e}>{e}</li>)}</ul>}
          <div className="mt-4 flex gap-2">
            <Button onClick={approve}><Check /> Approve & create</Button>
            <Button variant="ghost" onClick={() => setDraft(null)}><X /> Discard</Button>
          </div>
        </div>
      )}

      <ul className="mt-5 grid gap-2 sm:grid-cols-2">
        {fields?.length === 0 && <li className="col-span-full rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">No extra fields yet. Try “add a patents held field”.</li>}
        {fields?.map((f) => (
          <li key={f.id} className={cn("flex items-center justify-between gap-3 rounded-xl border border-border bg-card p-3", !f.active && "opacity-55")}>
            <div className="min-w-0">
              <p className="font-medium">{f.label} <code className="ml-1 text-xs text-muted-foreground">{f.key}</code></p>
              <p className="text-xs text-muted-foreground">{f.type}{f.options.length ? ` · ${f.options.join(", ")}` : ""}{f.searchable ? " · searchable" : ""}{f.created_by === "shilpkar" ? " · built by Shilpkar" : ""}</p>
            </div>
            <Switch checked={f.active} aria-label={f.active ? `Hide ${f.label}` : `Show ${f.label}`}
              onCheckedChange={async (v) => { await api(`/v1/admin/fields/${f.id}`, { method: "PATCH", json: { active: v } }); load(); }} />
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">Hiding a field keeps every stored value — nothing is ever deleted by a configuration change.</p>
    </section>
  );
}

// ------------------------------------------------------------------ plugins (code)
function PluginsSection() {
  const [request, setRequest] = useState("");
  const [changes, setChanges] = useState<Change[] | null>(null);
  const [plugins, setPlugins] = useState<{ enabled: boolean; plugins: { slug: string; prefix: string; doc: string }[] } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    const [c, p] = await Promise.all([
      api<Change[]>("/v1/admin/builder/changes").catch(() => []),
      api<{ enabled: boolean; plugins: { slug: string; prefix: string; doc: string }[] }>("/v1/admin/builder/plugins").catch(() => null),
    ]);
    setChanges(c);
    setPlugins(p);
    return c;
  }, []);

  // While anything is still being checked, poll until it reaches a final state.
  useEffect(() => {
    load();
    timer.current = setInterval(async () => {
      const c = await load();
      if (!c.some((x) => x.status === "proposed") && timer.current) { clearInterval(timer.current); timer.current = null; }
    }, 2000);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [load]);

  function poll() {
    if (timer.current) return;
    timer.current = setInterval(async () => {
      const c = await load();
      if (!c.some((x) => x.status === "proposed") && timer.current) { clearInterval(timer.current); timer.current = null; }
    }, 2000);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy("new");
    try {
      await api("/v1/admin/builder/changes", { method: "POST", json: { request } });
      setRequest("");
      await load();
      poll();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't start");
    } finally { setBusy(null); }
  }

  async function act(c: Change, action: "apply" | "reject") {
    setBusy(c.id);
    try {
      await api(`/v1/admin/builder/changes/${c.id}/${action}`, { method: "POST" });
      toast.success(action === "apply" ? `Plugin “${c.slug}” is live at /v1/plugins/${c.slug}` : "Rejected");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    } finally { setBusy(null); }
  }

  return (
    <section aria-labelledby="plugins-h">
      <h2 id="plugins-h" className="text-2xl font-semibold">Plugins <span className="text-sm font-normal text-muted-foreground">· AI-written code, three locks</span></h2>
      <ol className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
        {[["1 · Code guard", "Allow-list only: read-only, public data, no files / network / reflection."],
          ["2 · Isolated sandbox", "Lint, security scan and tests in a container with no network."],
          ["3 · Your approval", "You read the code and click approve. Only then does it load."]].map(([t, d]) => (
          <li key={t} className="rounded-xl bg-muted/60 p-3"><p className="font-medium">{t}</p><p className="text-xs text-muted-foreground">{d}</p></li>
        ))}
      </ol>
      {plugins && !plugins.enabled && (
        <p className="mt-3 rounded-xl bg-pending-soft p-3 text-sm">Plugins are switched off on this server, so approving is disabled. Set <code>PLUGINS_ENABLED=true</code> to allow them.</p>
      )}

      <form onSubmit={submit} className="mt-4">
        <Textarea value={request} onChange={(e) => setRequest(e.target.value)} rows={2} className="text-base" aria-label="Describe the plugin you want"
          placeholder="e.g. make an endpoint showing the number of members in each state" />
        <Button type="submit" className="mt-2" disabled={busy === "new" || request.trim().length < 5}><Hammer /> Build it</Button>
      </form>

      <ul className="mt-6 space-y-4">
        {changes?.length === 0 && <li className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">No plugin requests yet.</li>}
        {changes?.map((c) => {
          const st = STATUS[c.status] ?? STATUS.proposed;
          const guard = c.checks.guard ?? [];
          const sb = c.checks.sandbox;
          return (
            <li key={c.id} className="rounded-2xl border border-border bg-card p-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium">{c.request}</p>
                  {c.summary && <p className="text-sm text-muted-foreground">{c.summary}</p>}
                </div>
                <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium", st.cls)}>
                  {c.status === "proposed" && <Loader2 className="size-3 animate-spin" />} {st.label}
                </span>
              </div>

              {(c.checks.history?.length ?? 0) > 0 && (
                <p className="mt-3 rounded-lg bg-indigo-soft/60 p-2.5 text-xs text-indigo">
                  <b>Self-repair:</b> {c.checks.attempts} automatic fix attempt(s). It failed {c.checks.history!.map((h) => `“${h.step}”`).join(", then ")}
                  {c.status === "ready" || c.status === "applied" ? ", read the error, and corrected its own code — every fix was re-checked from scratch." : " and could not fix it within the limit of two attempts."}
                </p>
              )}
              {c.status !== "proposed" && (
                <ul className="mt-3 space-y-1.5 text-sm">
                  <li className="flex items-center gap-2">
                    {guard.length === 0 ? <CircleCheck className="size-4 text-verified" /> : <CircleX className="size-4 text-destructive" />}
                    Code guard {guard.length === 0 ? "passed" : "blocked it"}
                  </li>
                  {guard.map((g) => <li key={g} className="ml-6 text-xs text-destructive">{g}</li>)}
                  {sb && !sb.ran && <li className="flex items-center gap-2"><CircleX className="size-4 text-destructive" /> Could not verify safely: {sb.reason}</li>}
                  {sb?.steps.map((s) => (
                    <li key={s.name}>
                      <span className="flex items-center gap-2">{s.ok ? <CircleCheck className="size-4 text-verified" /> : <CircleX className="size-4 text-destructive" />} {s.name}</span>
                      {!s.ok && <pre tabIndex={0} className="ml-6 mt-1 max-h-40 overflow-auto rounded-lg bg-muted p-2 text-[11px]">{s.output}</pre>}
                    </li>
                  ))}
                </ul>
              )}

              {Object.keys(c.files).length > 0 && (
                <div className="mt-3">
                  <button className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground" onClick={() => setOpen(open === c.id ? null : c.id)}>
                    <FileCode2 className="size-4" /> {open === c.id ? "Hide" : "Read"} the code ({Object.keys(c.files).length} files)
                  </button>
                  {open === c.id && Object.entries(c.files).map(([path, src]) => (
                    <div key={path} className="mt-2"><p className="mb-1 font-mono text-xs text-muted-foreground">{path}</p><CodeBlock code={src} language="python" /></div>
                  ))}
                </div>
              )}

              {c.status === "ready" && (
                <div className="mt-4 flex gap-2">
                  <Button disabled={busy === c.id || plugins?.enabled === false} onClick={() => act(c, "apply")}><Rocket /> Approve & go live</Button>
                  <Button variant="outline" disabled={busy === c.id} onClick={() => act(c, "reject")}>Reject</Button>
                </div>
              )}
              {c.status === "applied" && (
                <Button className="mt-4" variant="outline" render={<a href={`${API_URL}/docs#/plugin%3A${c.slug}`} target="_blank" rel="noreferrer" />} nativeButton={false}>
                  <ExternalLink /> Try /v1/plugins/{c.slug}
                </Button>
              )}
            </li>
          );
        })}
      </ul>

      {plugins && plugins.plugins.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold">Live plugins</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {plugins.plugins.map((p) => <li key={p.slug}><code>{p.prefix}</code> <span className="text-muted-foreground">— {p.doc}</span></li>)}
          </ul>
        </div>
      )}
      <p className="mt-6 text-xs text-muted-foreground">Looking for what the agents are doing right now? <Link href="/mission-control" className="underline">Mission Control</Link>.</p>
    </section>
  );
}
