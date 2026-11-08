"use client";

import { useCallback, useEffect, useState } from "react";
import { CircleCheck, CircleX, Send, Trash2, Webhook as WebhookIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CopyButton } from "./code";

interface Hook { id: string; url: string; events: string[]; active: boolean; created_at: string }
interface EventInfo { name: string; description: string; admin_only: boolean }
interface Delivery { delivery_id: string; event: string; attempt: number; status_code: number | null; ok: boolean; error: string; duration_ms: number; created_at: string }

export function Webhooks() {
  const { user } = useAuth();
  const [hooks, setHooks] = useState<Hook[] | null>(null);
  const [events, setEvents] = useState<EventInfo[]>([]);
  const [url, setUrl] = useState("");
  const [chosen, setChosen] = useState<string[]>(["certificate.issued"]);
  const [secret, setSecret] = useState<{ id: string; value: string } | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [log, setLog] = useState<Delivery[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => api<Hook[]>("/v1/webhooks").then(setHooks).catch(() => setHooks([])), []);
  useEffect(() => {
    load();
    api<EventInfo[]>("/v1/webhooks/events", { auth: false }).then(setEvents).catch(() => {});
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy("create");
    try {
      const h = await api<Hook & { secret: string }>("/v1/webhooks", { method: "POST", json: { url: url.trim(), events: chosen } });
      setSecret({ id: h.id, value: h.secret });
      setUrl("");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't create the webhook");
    } finally { setBusy(null); }
  }

  async function test(h: Hook) {
    setBusy(h.id);
    try {
      const r = await api<{ ok: boolean; status_code: number | null; error: string }>(`/v1/webhooks/${h.id}/test`, { method: "POST" });
      if (r.ok) toast.success(`Your endpoint answered ${r.status_code}`);
      else toast.error(`Delivery failed: ${r.error || r.status_code}`);
      if (open === h.id) showLog(h.id);
    } finally { setBusy(null); }
  }

  async function showLog(id: string) {
    setOpen(id);
    setLog(await api<Delivery[]>(`/v1/webhooks/${id}/deliveries`).catch(() => []));
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_1.3fr]">
      <form onSubmit={create} className="space-y-4 rounded-2xl border border-border bg-card p-5">
        <h3 className="flex items-center gap-2 text-lg font-semibold"><WebhookIcon className="size-5 text-primary" /> New webhook</h3>
        <div className="space-y-1.5">
          <Label htmlFor="hook-url">Endpoint URL (https)</Label>
          <Input id="hook-url" required type="url" placeholder="https://example.com/hooks/pramaan" value={url} onChange={(e) => setUrl(e.target.value)} className="h-10" />
          <p className="text-xs text-muted-foreground">Private and internal addresses are blocked.</p>
        </div>
        <fieldset className="space-y-2">
          <legend className="mb-1 text-sm font-medium">Events</legend>
          {events.filter((e) => !e.admin_only || user?.role === "admin").map((e) => (
            <label key={e.name} className="flex cursor-pointer items-start gap-2 text-sm">
              <Checkbox className="mt-0.5" checked={chosen.includes(e.name)} onCheckedChange={(v) => setChosen(v ? [...chosen, e.name] : chosen.filter((x) => x !== e.name))} />
              <span><code className="text-xs">{e.name}</code><span className="block text-xs text-muted-foreground">{e.description}</span></span>
            </label>
          ))}
        </fieldset>
        <Button type="submit" disabled={busy === "create" || !url || chosen.length === 0}>Create webhook</Button>
      </form>

      <div className="space-y-4">
        {secret && (
          <div className="rounded-2xl border-2 border-verified bg-verified-soft p-4" role="alert">
            <p className="font-semibold">Signing secret — shown only once</p>
            <p className="text-sm text-muted-foreground">Use it to verify the <code>X-Pramaan-Signature</code> header on every delivery.</p>
            <div className="mt-2 flex items-center gap-2">
              <code className="min-w-0 flex-1 break-all rounded-lg bg-background p-2 text-xs">{secret.value}</code>
              <CopyButton text={secret.value} />
            </div>
            <button className="mt-2 text-xs text-muted-foreground underline" onClick={() => setSecret(null)}>I&apos;ve saved it</button>
          </div>
        )}
        <h3 className="text-lg font-semibold">Your webhooks</h3>
        {hooks && hooks.length === 0 && <p className="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">No webhooks yet.</p>}
        <ul className="space-y-2">
          {hooks?.map((h) => (
            <li key={h.id} className="rounded-xl border border-border bg-card p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-mono text-sm">{h.url}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{h.events.join(", ")}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Switch checked={h.active} aria-label={h.active ? "Pause webhook" : "Resume webhook"}
                    onCheckedChange={async (v) => { await api(`/v1/webhooks/${h.id}`, { method: "PATCH", json: { active: v } }); load(); }} />
                  <Button variant="ghost" size="icon" aria-label="Send a test event" disabled={busy === h.id} onClick={() => test(h)}><Send /></Button>
                  <Button variant="ghost" size="icon" aria-label="Delete webhook"
                    onClick={async () => { if (confirm("Delete this webhook?")) { await api(`/v1/webhooks/${h.id}`, { method: "DELETE" }); load(); } }}><Trash2 /></Button>
                </div>
              </div>
              <button className="mt-1 text-xs text-muted-foreground underline" onClick={() => (open === h.id ? setOpen(null) : showLog(h.id))}>
                {open === h.id ? "Hide" : "Show"} deliveries
              </button>
              {open === h.id && (
                <ul className="mt-2 space-y-1 text-xs">
                  {log.length === 0 && <li className="text-muted-foreground">Nothing delivered yet — press the send icon to try.</li>}
                  {log.map((d, i) => (
                    <li key={i} className="flex items-center gap-2">
                      {d.ok ? <CircleCheck className="size-3.5 text-verified" /> : <CircleX className="size-3.5 text-destructive" />}
                      <code>{d.event}</code> <span className="text-muted-foreground">attempt {d.attempt} · {d.status_code ?? d.error} · {d.duration_ms} ms · {new Date(d.created_at).toLocaleTimeString()}</span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
