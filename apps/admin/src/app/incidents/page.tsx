"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

interface Proposal { title?: string; rationale?: string; diff?: string; problems?: string[]; checked?: boolean; needs?: string; next?: string }
interface Incident { id: string; signature: string; summary: string; count: number; status: string; first_seen: string; last_seen: string; proposal: Proposal }

const STATUS_TEXT: Record<string, string> = { open: "Open", patch_proposed: "Patch proposed", resolved: "Resolved", dismissed: "Dismissed" };

/** Spikes of agent failures and the fixer's proposals. A proposal is a diff to READ: nothing here applies, merges or deploys code. */
export default function IncidentsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Incident[] | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) router.push("/login");
    else setError(e instanceof Error ? e.message : "Something went wrong");
  }, [router]);
  const load = useCallback(() => api<Incident[]>("/v1/admin/incidents").then(setItems).catch(fail), [fail]);
  useEffect(() => { void load(); }, [load]);

  async function run(label: string, path: string, json?: unknown) {
    setError(""); setMsg(""); setBusy(label);
    try {
      const r = await api<Record<string, unknown>>(path, { method: "POST", json });
      setMsg(label === "scan" ? `Scan done: ${r.signals} spike(s), ${r.opened} new incident(s).` : r.ok === false ? "No safe patch was proposed." : "Done.");
      await load();
    } catch (e) { fail(e); } finally { setBusy(""); }
  }

  return (
    <main>
      <div className="row"><Link href="/">Queue</Link><h1 className="grow">Incidents</h1>
        <button className="secondary" onClick={() => run("scan", "/v1/admin/incidents/scan")} disabled={busy !== ""}>Scan now</button></div>
      {error && <p className="err" role="alert">{error}</p>}
      {msg && <p className="panel" role="status">{msg}</p>}
      <p className="muted">A spike is at least 5 failed agent runs, at least 30% of that workflow, with the same kind of error. The fixer only proposes: a person makes the pull request and reviews it.</p>
      {items === null ? <p className="muted">Loading...</p> : items.length === 0 ? <p className="panel">No incidents.</p> : items.map((i) => (
        <section key={i.id} className="panel" aria-label={i.signature}>
          <div className="row"><strong className="grow">{i.signature}</strong><span className="chip">{STATUS_TEXT[i.status] ?? i.status}</span></div>
          <p>{i.count} failed runs. Last seen {new Date(i.last_seen).toLocaleString()}.</p>
          <p className="muted">{i.summary}</p>
          {i.proposal.diff ? (
            <details>
              <summary>Proposed patch: {i.proposal.title}</summary>
              <p>{i.proposal.rationale}</p>
              <pre style={{ overflow: "auto", whiteSpace: "pre-wrap" }}>{i.proposal.diff}</pre>
              <p className="muted">{i.proposal.needs}. Next: <code>{i.proposal.next}</code></p>
            </details>
          ) : i.proposal.problems?.length ? <p className="muted">No patch kept: {i.proposal.problems.join("; ")}</p> : null}
          <div className="row">
            <button className="secondary" onClick={() => run(`p${i.id}`, `/v1/admin/incidents/${i.id}/propose`)} disabled={busy !== "" || i.status !== "open"}>Propose a patch</button>
            <button className="secondary" onClick={() => run(`s${i.id}`, `/v1/admin/incidents/${i.id}/status`, { status: "resolved" })} disabled={busy !== ""}>Mark resolved</button>
            <button className="secondary" onClick={() => run(`d${i.id}`, `/v1/admin/incidents/${i.id}/status`, { status: "dismissed" })} disabled={busy !== ""}>Dismiss</button>
          </div>
        </section>
      ))}
    </main>
  );
}
