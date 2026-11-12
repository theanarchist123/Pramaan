"use client";

import { useCallback, useEffect, useState } from "react";
import { KeyRound, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { CopyButton } from "./code";

interface Key {
  id: string;
  name: string;
  prefix: string;
  mode: "live" | "test";
  scopes: string[];
  rate_limit_per_min: number;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

const READ_ONLY = ["verify:read", "profiles:read", "search:read"];
const SCOPES: [string, string][] = [
  ["verify:read", "Verify certificates"],
  ["profiles:read", "Read your own profiles"],
  ["profiles:write", "Create & edit profiles"],
  ["search:read", "Search the registry"],
  ["webhooks:manage", "Manage webhooks"],
];

interface Usage { days: { day: string; requests: number; throttled: number }[]; total: number; throttled: number }

/** Seven days of requests as bars, with the numbers in text: the bars are decoration, the words are the information. */
function UsageBars({ id }: { id: string }) {
  const [u, setU] = useState<Usage | null>(null);
  useEffect(() => { api<Usage>(`/v1/api-keys/${id}/usage?days=7`).then(setU).catch(() => setU(null)); }, [id]);
  if (!u) return null;
  const max = Math.max(1, ...u.days.map((d) => d.requests));
  return (
    <div className="mt-2">
      <div className="flex h-6 items-end gap-0.5" aria-hidden="true">
        {u.days.map((d) => <span key={d.day} className="w-3 rounded-sm bg-primary/60" style={{ height: `${Math.max(8, (d.requests / max) * 100)}%`, opacity: d.requests ? 1 : 0.25 }} />)}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {u.total} request{u.total === 1 ? "" : "s"} in the last 7 days{u.throttled ? `, ${u.throttled} refused for going over the limit` : ""}
      </p>
    </div>
  );
}

export function ApiKeys() {
  const [keys, setKeys] = useState<Key[] | null>(null);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["verify:read", "search:read", "profiles:read"]);
  const [limit, setLimit] = useState(60);
  const [test, setTest] = useState(false);
  const [fresh, setFresh] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api<Key[]>("/v1/api-keys").then(setKeys).catch(() => setKeys([])), []);
  useEffect(() => void load(), [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api<Key & { key: string }>("/v1/api-keys", {
        method: "POST", json: { name: name.trim(), scopes: test ? scopes.filter((x) => READ_ONLY.includes(x)) : scopes, rate_limit_per_min: limit, mode: test ? "test" : "live" },
      });
      setFresh(r.key);
      setName("");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't create the key");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(k: Key) {
    if (!confirm(`Revoke “${k.name}”? Anything using it will stop working immediately.`)) return;
    await api(`/v1/api-keys/${k.id}`, { method: "DELETE" });
    toast.success("Key revoked");
    load();
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
      <form onSubmit={create} className="space-y-4 rounded-2xl border border-border bg-card p-5">
        <h3 className="flex items-center gap-2 text-lg font-semibold"><KeyRound className="size-5 text-primary" /> New API key</h3>
        <div className="space-y-1.5">
          <Label htmlFor="key-name">Name</Label>
          <Input id="key-name" required maxLength={120} placeholder="e.g. My Telegram bot" value={name} onChange={(e) => setName(e.target.value)} className="h-10" />
        </div>
        <fieldset className="space-y-2">
          <legend className="mb-1 text-sm font-medium">Permissions</legend>
          {SCOPES.filter(([s]) => !test || READ_ONLY.includes(s)).map(([s, label]) => (
            <label key={s} className="flex cursor-pointer items-center gap-2 text-sm">
              <Checkbox checked={scopes.includes(s)} onCheckedChange={(v) => setScopes(v ? [...scopes, s] : scopes.filter((x) => x !== s))} />
              <span>{label}</span> <code className="text-xs text-muted-foreground">{s}</code>
            </label>
          ))}
        </fieldset>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <Checkbox checked={test} onCheckedChange={(v) => setTest(Boolean(v))} />
          <span>Test key: can only read, safe to put in a CI job or a demo</span>
        </label>
        <div className="space-y-1.5">
          <Label htmlFor="key-limit">Rate limit (requests / minute)</Label>
          <Input id="key-limit" type="number" min={1} max={6000} value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="h-10 w-32" />
        </div>
        <Button type="submit" disabled={busy || !name.trim() || scopes.length === 0}>Create key</Button>
      </form>

      <div className="space-y-4">
        {fresh && (
          <div className="rounded-2xl border-2 border-verified bg-verified-soft p-4" role="alert">
            <p className="font-semibold">Copy your key now — it won&apos;t be shown again.</p>
            <div className="mt-2 flex items-center gap-2">
              <code className="min-w-0 flex-1 break-all rounded-lg bg-background p-2 text-xs">{fresh}</code>
              <CopyButton text={fresh} />
            </div>
            <button className="mt-2 text-xs text-muted-foreground underline" onClick={() => setFresh(null)}>I&apos;ve saved it</button>
          </div>
        )}
        <h3 className="text-lg font-semibold">Your keys</h3>
        {keys === null ? null : keys.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">No keys yet. Public endpoints work without one.</p>
        ) : (
          <ul className="space-y-2">
            {keys.map((k) => (
              <li key={k.id} className="flex items-start justify-between gap-3 rounded-xl border border-border bg-card p-3">
                <div className="min-w-0">
                  <p className="font-medium">{k.name} {k.revoked_at && <span className="ml-1 rounded bg-destructive/10 px-1.5 py-0.5 text-xs text-destructive">revoked</span>}</p>
                  <p className="font-mono text-xs text-muted-foreground">pk_{k.mode}_{k.prefix}_••••••••</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {k.scopes.join(", ")} · {k.rate_limit_per_min}/min · {k.last_used_at ? `last used ${new Date(k.last_used_at).toLocaleString()}` : "never used"}
                  </p>
                  <UsageBars id={k.id} />
                </div>
                {!k.revoked_at && (
                  <Button variant="ghost" size="icon" aria-label={`Revoke ${k.name}`} onClick={() => revoke(k)}><Trash2 /></Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
