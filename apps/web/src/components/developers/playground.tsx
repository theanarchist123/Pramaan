"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { API_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { CodeBlock, CopyButton } from "./code";

interface Preset { label: string; method: string; path: string; body?: string; auth?: boolean }

const BASE_PRESETS: Preset[] = [
  { label: "Verify a certificate", method: "GET", path: "/v1/verify/{code}" },
  { label: "Search in plain English", method: "POST", path: "/v1/search", body: '{\n  "query": "clean-energy innovators in Karnataka who have collaborated with universities",\n  "limit": 3\n}' },
  { label: "Try to forge a certificate", method: "POST", path: "/v1/verify/check", body: '{\n  "code": "{code}",\n  "payload": { "v": 1, "full_name": "Someone Else", "claims": [] }\n}' },
  { label: "List verified people", method: "GET", path: "/v1/profiles?limit=3" },
  { label: "Relationship graph", method: "GET", path: "/v1/graph" },
  { label: "Members by state", method: "GET", path: "/v1/stats/map" },
  { label: "Audit the transparency log", method: "GET", path: "/v1/transparency/verify" },
  { label: "Signing public key", method: "GET", path: "/.well-known/pramaan-keys.json" },
  { label: "Webhook event catalogue", method: "GET", path: "/v1/webhooks/events" },
  { label: "My profiles (needs auth)", method: "GET", path: "/v1/profiles/mine", auth: true },
];

interface Result { status: number; ms: number; headers: [string, string][]; body: string }

export function Playground() {
  const { user } = useAuth();
  const [code, setCode] = useState("PRM-XXXXXXXXXX");
  const [idx, setIdx] = useState(0);
  const [shell, setShell] = useState<"curl" | "powershell">("curl");
  useEffect(() => {
    if (/win/i.test(navigator.platform) || /windows/i.test(navigator.userAgent)) setShell("powershell");
  }, []);
  const [method, setMethod] = useState("GET");
  const [path, setPath] = useState(BASE_PRESETS[0].path);
  const [body, setBody] = useState("");
  const [authMode, setAuthMode] = useState<"none" | "session" | "key">("none");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Result | null>(null);

  // Prefill with a real certificate so the very first click works.
  useEffect(() => {
    fetch(`${API_URL}/v1/transparency?limit=1`).then((r) => r.json()).then((l) => l[0] && setCode(l[0].certificate_code)).catch(() => {});
  }, []);

  const fill = useCallback((s: string) => s.replaceAll("{code}", code), [code]);
  function pick(i: number) {
    const p = BASE_PRESETS[i];
    setIdx(i);
    setMethod(p.method);
    setPath(p.path);
    setBody(p.body ?? "");
    if (p.auth && authMode === "none") setAuthMode(user ? "session" : "key");
  }
  useEffect(() => pick(idx), [code]); // eslint-disable-line react-hooks/exhaustive-deps -- re-apply the preset when the real code arrives

  const headers = useMemo(() => {
    const h: Record<string, string> = {};
    if (body && method !== "GET") h["Content-Type"] = "application/json";
    if (authMode === "key" && key) h["X-API-Key"] = key;
    return h;
  }, [authMode, key, body, method]);

  const powershell = useMemo(() => {
    const q = (t: string) => t.replace(/'/g, "''"); // PowerShell single-quoted strings escape ' as ''
    const parts = [`Invoke-RestMethod -Method ${method} -Uri "${API_URL}${fill(path)}"`];
    const hs = Object.entries(headers).filter(([k]) => k !== "Content-Type");
    if (hs.length) parts.push(`-Headers @{ ${hs.map(([k, v]) => `"${k}" = '${k === "Authorization" ? "Bearer <token>" : q(v)}'`).join("; ")} }`);
    if (body && method !== "GET") parts.push(`-ContentType "application/json"`, `-Body '${q(fill(body).replace(/\s*\n\s*/g, " "))}'`);
    return parts.join(" `\n  ");
  }, [method, path, body, headers, fill]);

  const curl = useMemo(() => {
    const parts = [`curl -X ${method} "${API_URL}${fill(path)}"`];
    for (const [k, v] of Object.entries(headers)) parts.push(`-H "${k}: ${k === "Authorization" ? "Bearer <token>" : v}"`);
    if (body && method !== "GET") parts.push(`-d '${fill(body).replace(/\s*\n\s*/g, " ")}'`);
    return parts.join(" \\\n  ");
  }, [method, path, body, headers, fill]);

  async function send() {
    setBusy(true);
    const t0 = performance.now();
    try {
      const r = await fetch(`${API_URL}${fill(path)}`, {
        method, headers, body: body && method !== "GET" ? fill(body) : undefined,
        credentials: authMode === "session" ? "include" : "omit", // "My session" = the httpOnly cookie

      });
      const text = await r.text();
      let pretty = text;
      try { pretty = JSON.stringify(JSON.parse(text), null, 2); } catch { /* not JSON (e.g. SVG) */ }
      setRes({
        status: r.status, ms: Math.round(performance.now() - t0), body: pretty.slice(0, 20000),
        headers: ["content-type", "retry-after", "cache-control"].flatMap((h) => (r.headers.get(h) ? [[h, r.headers.get(h)!] as [string, string]] : [])),
      });
    } catch {
      setRes({ status: 0, ms: Math.round(performance.now() - t0), headers: [], body: "Network error: is the API running?" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium" htmlFor="pg-preset">Example request</label>
          <select id="pg-preset" value={idx} onChange={(e) => pick(Number(e.target.value))} className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm">
            {BASE_PRESETS.map((p, i) => <option key={p.label} value={i}>{p.method} · {p.label}</option>)}
          </select>
        </div>
        <div className="flex gap-2">
          <select aria-label="Method" value={method} onChange={(e) => setMethod(e.target.value)} className="h-10 rounded-lg border border-input bg-background px-2 text-sm font-medium">
            {["GET", "POST", "PATCH", "DELETE"].map((m) => <option key={m}>{m}</option>)}
          </select>
          <Input aria-label="Path" value={path} onChange={(e) => setPath(e.target.value)} className="h-10 font-mono text-sm" />
        </div>
        {method !== "GET" && method !== "DELETE" && (
          <Textarea aria-label="JSON body" value={body} onChange={(e) => setBody(e.target.value)} rows={7} className="font-mono text-sm" spellCheck={false} />
        )}
        <fieldset className="flex flex-wrap items-center gap-3 text-sm">
          <legend className="sr-only">Authentication</legend>
          <span className="font-medium">Auth:</span>
          {([["none", "None (public)"], ["session", "My session"], ["key", "API key"]] as const).map(([m, label]) => (
            <label key={m} className="flex cursor-pointer items-center gap-1.5">
              <input type="radio" name="auth" checked={authMode === m} onChange={() => setAuthMode(m)} disabled={m === "session" && !user} /> {label}
            </label>
          ))}
        </fieldset>
        {authMode === "key" && <Input aria-label="API key" placeholder="pk_live_…" value={key} onChange={(e) => setKey(e.target.value)} className="h-10 font-mono text-sm" type="password" />}
        <div className="flex items-center gap-2">
          <Button onClick={send} disabled={busy} className="h-10 px-5">{busy ? <Loader2 className="animate-spin" /> : <Play />} Send request</Button>
          <span className="text-xs text-muted-foreground">Runs in your browser, against {API_URL}</span>
        </div>
        <div>
          <div className="mb-1 flex items-center justify-between gap-2 text-sm font-medium">
            <span className="flex items-center gap-1" role="group" aria-label="Command style">
              {(["curl", "powershell"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  aria-pressed={shell === k}
                  onClick={() => setShell(k)}
                  className={cn("rounded-md px-2 py-0.5 text-xs", shell === k ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted")}
                >
                  {k === "curl" ? "curl (bash)" : "PowerShell"}
                </button>
              ))}
            </span>
            <CopyButton text={shell === "curl" ? curl : powershell} />
          </div>
          <pre tabIndex={0} className="overflow-x-auto rounded-xl bg-muted p-3 text-xs">{shell === "curl" ? curl : powershell}</pre>
        </div>
      </div>

      <div aria-live="polite">
        <div className="mb-2 flex items-center gap-3 text-sm">
          <span className="font-medium">Response</span>
          {res && (
            <>
              <span className={cn("rounded-md px-2 py-0.5 font-mono text-xs font-semibold",
                res.status >= 200 && res.status < 300 ? "bg-verified-soft text-verified" : "bg-destructive/10 text-destructive")}>
                {res.status || "ERR"}
              </span>
              <span className="text-xs text-muted-foreground">{res.ms} ms</span>
              {res.headers.map(([k, v]) => <span key={k} className="hidden text-xs text-muted-foreground sm:inline">{k}: {v}</span>)}
            </>
          )}
        </div>
        {res ? <CodeBlock code={res.body} language="json" className="[&_pre]:max-h-[34rem]" />
          : <p className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">Pick an example and press <b>Send request</b>.</p>}
      </div>
    </div>
  );
}
