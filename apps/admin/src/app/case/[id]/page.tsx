"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

interface Evidence { id: string; kind: string; url: string; quote: string }
interface Claim { id: string; field: string; value: string; year: number | null; status: string; evidence: Evidence[] }
interface Doc { id: string; filename: string; match_score: number | null; holder_name: string; title: string; issuer: string; flags: string[]; flag_notes: string[] }
interface Detail {
  item: { id: string; reason: string; status: string; sla_due_at: string | null; details: { reason_codes?: string[] } };
  profile: { id: string; full_name: string; sector: string; state: string; headline: string; bio: string; claims: Claim[]; wikidata_qid?: string } | null;
  documents: Doc[];
  permissions: { can_decide: boolean; holds_lock: boolean; own_profile: boolean };
}
interface Namesakes { confirmed_qid: string; candidates: { qid: string; label: string; description: string }[] }
type Decision = "verify" | "hold" | "reject";
interface Per { decision: Decision; code: string; note: string; ref: string }

const STATUS_TEXT: Record<string, string> = {
  self: "Self-claimed", web: "Public source", document: "Document", human: "Confirmed by a reviewer", issuer: "Issuer",
};

/** The reviewer's workbench for one case: claims with their evidence, documents and flags, namesakes, and the decision form. */
export default function CasePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [d, setD] = useState<Detail | null>(null);
  const [codes, setCodes] = useState<string[]>([]);
  const [namesakes, setNamesakes] = useState<Namesakes | null>(null);
  const [per, setPer] = useState<Record<string, Per>>({});
  const [focus, setFocus] = useState(0);
  const [outcome, setOutcome] = useState<"approve" | "reject" | "hold">("hold");
  const [code, setCode] = useState("EVIDENCE_CHECKED");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [detail, rc] = await Promise.all([api<Detail>(`/v1/admin/review/${id}`), api<string[]>("/v1/admin/review/reason-codes")]);
      setD(detail);
      setCodes(rc);
      api<Namesakes>(`/v1/admin/review/${id}/namesakes`).then(setNamesakes).catch(() => setNamesakes(null));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Couldn't load the case");
    }
  }, [id, router]);
  useEffect(() => { void load(); }, [load]);

  const claims = useMemo(() => d?.profile?.claims ?? [], [d]);
  const setFor = (cid: string, patch: Partial<Per>) =>
    setPer((p) => {
      const base: Per = p[cid] ?? { decision: "hold", code: "EVIDENCE_CHECKED", note: "", ref: "" };
      return { ...p, [cid]: { ...base, ...patch } };
    });

  async function take() {
    setError("");
    try {
      await api(`/v1/admin/review/${id}/claim`, { method: "POST" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't take the case");
    }
  }

  async function submit() {
    if (!d?.permissions.can_decide || busy) return;
    setBusy(true);
    setError("");
    try {
      const chosen = Object.entries(per).filter(([, p]) => p.decision !== "hold" || p.note || p.ref);
      await api(`/v1/admin/review/${id}/decide`, {
        method: "POST",
        json: {
          outcome, reason_code: code, note,
          claims: chosen.map(([claim_id, p]) => ({ claim_id, decision: p.decision, reason_code: p.code, note: p.note, evidence_ref: p.ref })),
        },
      });
      if (outcome === "hold") await load();
      else router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save the decision");
    } finally {
      setBusy(false);
    }
  }

  // Keyboard: j/k move between claims, v/h/x set verify/hold/reject on the focused claim, Ctrl+Enter saves. Ignored while typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = /INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName);
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        void submit();
        return;
      }
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "j") setFocus((f) => Math.min(claims.length - 1, f + 1));
      else if (e.key === "k") setFocus((f) => Math.max(0, f - 1));
      else if (claims[focus] && (e.key === "v" || e.key === "h" || e.key === "x"))
        setFor(claims[focus].id, { decision: e.key === "v" ? "verify" : e.key === "h" ? "hold" : "reject" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (error && !d) return <main><p className="err" role="alert">{error}</p><Link href="/">Back to the queue</Link></main>;
  if (!d) return <main><p className="muted">Loading...</p></main>;
  const p = d.profile;
  const closed = d.item.status !== "open";

  return (
    <main>
      <div className="row">
        <Link href="/">Queue</Link>
        <h1 className="grow">{p?.full_name ?? "(profile removed)"}</h1>
        {!d.permissions.holds_lock && !closed && !d.permissions.own_profile && <button onClick={take}>Take case</button>}
        {d.permissions.holds_lock && <span className="chip">You hold this case</span>}
      </div>
      <p className="muted">{[p?.sector, p?.state].filter(Boolean).join(" · ")}{p?.headline ? ` · ${p.headline}` : ""}</p>
      {d.permissions.own_profile && <p className="err" role="alert">This is your own profile. You cannot review it.</p>}
      {error && <p className="err" role="alert">{error}</p>}

      <div className="panel">
        <strong>Why it is here</strong>
        <div>{(d.item.details.reason_codes ?? []).map((c) => <span className="chip" key={c}>{c}</span>)}</div>
        <p className="muted">{d.item.reason}</p>
      </div>

      <div className="panel" aria-label="Claims">
        <div className="row">
          <strong className="grow">Claims</strong>
          <span className="muted">j / k move, v verify, h hold, x reject, Ctrl+Enter save</span>
        </div>
        {claims.length === 0 && <p className="muted">No claims.</p>}
        {claims.map((c, i) => {
          const cur = per[c.id];
          const need = cur?.decision === "verify" && (cur.note.trim().length < 10 || cur.ref.trim().length < 5);
          return (
            <section key={c.id} className={`claim${i === focus ? " focused" : ""}`} onClick={() => setFocus(i)} aria-current={i === focus}>
              <div className="row">
                <span className="grow"><strong>{c.field}</strong>{c.year ? ` (${c.year})` : ""}: {c.value}</span>
                <span className="chip">{STATUS_TEXT[c.status] ?? c.status}</span>
              </div>
              {c.evidence.filter((e) => e.kind !== "chat").map((e) => (
                <blockquote key={e.id} className="muted">
                  &ldquo;{e.quote}&rdquo; <em>{e.kind === "document" ? "(from a document)" : "(from a public source)"}</em>
                </blockquote>
              ))}
              {!closed && d.permissions.can_decide && (
                <div className="row">
                  <label className="inline">Decision
                    <select value={cur?.decision ?? "hold"} onChange={(e) => setFor(c.id, { decision: e.target.value as Decision })}>
                      <option value="hold">Hold</option>
                      <option value="verify">Verify</option>
                      <option value="reject">Reject</option>
                    </select>
                  </label>
                  <label className="inline">Reason
                    <select value={cur?.code ?? "EVIDENCE_CHECKED"} onChange={(e) => setFor(c.id, { code: e.target.value })}>
                      {codes.map((x) => <option key={x}>{x}</option>)}
                    </select>
                  </label>
                  {cur?.decision === "verify" && (
                    <>
                      <input aria-label="What you checked" placeholder="What you checked (10+ characters)" value={cur.note} onChange={(e) => setFor(c.id, { note: e.target.value })} />
                      <input aria-label="Evidence reference" placeholder="Evidence link or case reference" value={cur.ref} onChange={(e) => setFor(c.id, { ref: e.target.value })} />
                    </>
                  )}
                </div>
              )}
              {need && <p className="warn">Verifying needs a note and an evidence reference.</p>}
            </section>
          );
        })}
      </div>

      <div className="panel" aria-label="Documents">
        <strong>Documents</strong>
        {d.documents.length === 0 ? <p className="muted">None uploaded.</p> : d.documents.map((doc) => (
          <div key={doc.id} className="claim">
            <div className="row">
              <span className="grow">{doc.filename}</span>
              {doc.match_score != null && <span className="muted">name match {Math.round(doc.match_score * 100)}%</span>}
            </div>
            <p className="muted">Holder: {doc.holder_name || "not read"} · Title: {doc.title || "not read"} · Issuer: {doc.issuer || "not read"}</p>
            {doc.flags.length === 0 ? <p className="muted">No flags.</p> : (
              <ul>{doc.flags.map((f, i) => <li key={f} className="warn">{f}{doc.flag_notes[i] ? `: ${doc.flag_notes[i]}` : ""}</li>)}</ul>
            )}
          </div>
        ))}
        <p className="muted">File contents are not shown here. Opening the original is a separate, logged step.</p>
      </div>

      <div className="panel" aria-label="Namesakes">
        <strong>People with the same name on Wikidata</strong>
        <p className="muted">Applicant confirmed: {namesakes?.confirmed_qid || p?.wikidata_qid || "no item confirmed"}</p>
        {namesakes && namesakes.candidates.length === 0 && <p className="muted">No other matches (or the lookup is switched off).</p>}
        <ul>
          {(namesakes?.candidates ?? []).map((n) => (
            <li key={n.qid}><code>{n.qid}</code> {n.label}: {n.description || "no description"}{n.qid === namesakes?.confirmed_qid ? " (the applicant's choice)" : ""}</li>
          ))}
        </ul>
      </div>

      {!closed && (
        <div className="panel" aria-label="Decision">
          <strong>Your decision</strong>
          {!d.permissions.can_decide && <p className="muted">{d.permissions.own_profile ? "You cannot decide on your own profile." : "Take the case to decide on it."}</p>}
          <div className="row">
            <label className="inline">Outcome
              <select disabled={!d.permissions.can_decide} value={outcome} onChange={(e) => setOutcome(e.target.value as typeof outcome)}>
                <option value="hold">Hold (keep it open)</option>
                <option value="approve">Approve</option>
                <option value="reject">Reject</option>
              </select>
            </label>
            <label className="inline">Reason
              <select disabled={!d.permissions.can_decide} value={code} onChange={(e) => setCode(e.target.value)}>
                {codes.map((x) => <option key={x}>{x}</option>)}
              </select>
            </label>
          </div>
          <label htmlFor="note">Note {outcome !== "hold" && "(required, 10+ characters)"}</label>
          <textarea id="note" disabled={!d.permissions.can_decide} value={note} onChange={(e) => setNote(e.target.value)} rows={3} />
          <p><button disabled={!d.permissions.can_decide || busy} onClick={submit}>{busy ? "Saving..." : "Save decision"}</button></p>
        </div>
      )}
      {closed && <p className="muted">This case is {d.item.status}.</p>}
    </main>
  );
}
