"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

interface View { id: string; slug: string; status: string; version: number; request: string; has_previous: boolean; has_pending_draft: boolean; spec: { title?: string; blocks?: unknown[] } }
interface Change { id: string; slug: string; status: string; summary: string; request: string; files: Record<string, string>; checks: { lint?: string[]; rehearsal?: { ok: boolean; problems: string[]; tables_added: string[]; seconds: number }; approvals?: string[]; release_note?: string } }

/** Tier T2 (views as data) and T3 (database migrations). Neither can change the live site by itself: a view needs a SECOND person to publish, a migration needs two people and then a pull request. */
export default function BuilderPage() {
  const router = useRouter();
  const [views, setViews] = useState<View[] | null>(null);
  const [changes, setChanges] = useState<Change[] | null>(null);
  const [vreq, setVreq] = useState("");
  const [mreq, setMreq] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) router.push("/login");
    else setError(e instanceof Error ? e.message : "Something went wrong");
  }, [router]);
  const load = useCallback(async () => {
    try {
      setViews(await api<View[]>("/v1/admin/views"));
      setChanges((await api<Change[]>("/v1/admin/builder/changes")).filter((c) => c.slug.startsWith("mig_")));
    } catch (e) { fail(e); }
  }, [fail]);
  useEffect(() => { void load(); }, [load]);

  async function act(label: string, path: string, json?: unknown, method: "POST" | "PUT" = "POST") {
    setError(""); setMsg(""); setBusy(true);
    try { await api(path, { method, json }); setMsg(label); await load(); } catch (e) { fail(e); } finally { setBusy(false); }
  }

  return (
    <main>
      <div className="row"><Link href="/">Queue</Link><h1 className="grow">Views and migrations</h1></div>
      {error && <p className="err" role="alert">{error}</p>}
      {msg && <p className="panel" role="status">{msg}</p>}

      <section className="panel" aria-label="Views">
        <strong>Views (tier T2)</strong>
        <p className="muted">A view is a page described as data from a fixed set of blocks. The designer drafts it; you cannot publish a view you proposed or last edited.</p>
        <label htmlFor="vreq">What should the page show?</label>
        <textarea id="vreq" rows={2} value={vreq} onChange={(e) => setVreq(e.target.value)} maxLength={500} />
        <div className="row"><button onClick={() => act("Draft created.", "/v1/admin/views", { request: vreq }).then(() => setVreq(""))} disabled={busy || vreq.trim().length < 5}>Draft a view</button></div>
        {views?.map((v) => (
          <div key={v.id} className="panel">
            <div className="row"><strong className="grow">{v.spec.title ?? v.slug}</strong><span className="chip">{v.status}{v.version ? ` v${v.version}` : ""}</span></div>
            <p className="muted">{v.request}</p>
            {v.has_pending_draft && <p className="warn">A newer draft is waiting for a second person.</p>}
            <div className="row">
              <button className="secondary" onClick={() => act("Published.", `/v1/admin/views/${v.id}/publish`)} disabled={busy || v.status === "archived"}>Publish</button>
              <button className="secondary" onClick={() => act("Rolled back.", `/v1/admin/views/${v.id}/rollback`)} disabled={busy || !v.has_previous}>Roll back</button>
              <button className="secondary" onClick={() => act("Archived.", `/v1/admin/views/${v.id}/archive`)} disabled={busy || v.status === "archived"}>Archive</button>
              {v.status === "published" && <a href={`/v/${v.slug}`} target="_blank" rel="noreferrer">Open</a>}
            </div>
          </div>
        ))}
      </section>

      <section className="panel" aria-label="Migrations">
        <strong>Database migrations (tier T3)</strong>
        <p className="muted">The designer drafts an expand-only migration. It is checked and rehearsed on a scratch copy. Two different people approve it, then a person adds it to the repository through a pull request. The app never runs it.</p>
        <label htmlFor="mreq">What should the database be able to store?</label>
        <textarea id="mreq" rows={2} value={mreq} onChange={(e) => setMreq(e.target.value)} maxLength={500} />
        <div className="row"><button onClick={() => act("Migration drafted and checked.", "/v1/admin/builder/migrations", { request: mreq }).then(() => setMreq(""))} disabled={busy || mreq.trim().length < 10}>Draft a migration</button></div>
        {changes?.map((c) => (
          <div key={c.id} className="panel">
            <div className="row"><strong className="grow">{c.slug}</strong><span className="chip">{c.status.replace(/_/g, " ")}</span></div>
            <p>{c.summary}</p>
            {c.checks.lint?.length ? <ul>{c.checks.lint.map((p) => <li key={p} className="warn">{p}</li>)}</ul> : null}
            {c.checks.rehearsal && <p className={c.checks.rehearsal.ok ? "" : "warn"}>Rehearsal {c.checks.rehearsal.ok ? "passed" : "failed"}: adds {c.checks.rehearsal.tables_added.join(", ") || "no tables"} in {c.checks.rehearsal.seconds}s.{c.checks.rehearsal.problems.map((p) => ` ${p}`)}</p>}
            <details><summary>The migration file</summary><pre style={{ overflow: "auto" }}>{Object.values(c.files)[0]}</pre></details>
            <p className="muted">Approvals: {c.checks.approvals?.length ?? 0} of 2.</p>
            {c.checks.release_note && <p role="note">{c.checks.release_note}</p>}
            <button className="secondary" onClick={() => act("Approval recorded.", `/v1/admin/builder/migrations/${c.id}/approve`)} disabled={busy || c.status !== "ready"}>Approve</button>
          </div>
        ))}
      </section>
    </main>
  );
}
