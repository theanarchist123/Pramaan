"use client";

import { useState } from "react";
import Link from "next/link";
import { api, API_URL } from "@/lib/api";
import { Avatar, Icon, PageHead, Pill } from "@/components/ui";
import { tileFor } from "@/lib/labels";

const WEB = process.env.NEXT_PUBLIC_WEB_URL ?? ""; // same origin: the public site and /staff share one address

interface Hit {
  id: string; slug: string; full_name: string; headline: string; sector: string; state: string; city: string;
  score: number; reasons: string[]; is_demo: boolean;
}
interface Resp { results: Hit[]; took_ms: number; relaxed: boolean }

const EXAMPLES = [
  "clean-energy innovators in Karnataka who collaborated with universities",
  "someone who teaches classical dance to underprivileged children",
  "journalists investigating river pollution",
];

/** The registry as a CRM: ask in plain words (the same hybrid search the public site uses), see why each person matched. */
export default function PeoplePage() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<Resp | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [inv, setInv] = useState({ name: "", email: "", note: "" });
  const [invBusy, setInvBusy] = useState(false);
  const [invMsg, setInvMsg] = useState("");
  const [invErr, setInvErr] = useState("");

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setInvBusy(true);
    setInvMsg("");
    setInvErr("");
    try {
      await api("/v1/admin/outreach/invite", { method: "POST", json: inv });
      setInvMsg("Draft created. Nothing is sent until you send it from Follow-ups.");
      setInv({ name: "", email: "", note: "" });
    } catch (e2) {
      setInvErr(e2 instanceof Error ? e2.message : "Couldn't create the invitation");
    } finally {
      setInvBusy(false);
    }
  }

  async function run(text: string) {
    if (!text.trim()) return;
    setBusy(true);
    setErr("");
    try {
      setRes(await api<Resp>("/v1/search", { method: "POST", json: { query: text.trim(), limit: 25 } }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <PageHead eyebrow="The registry" title="People" lead={<>Ask in plain words. Each result says why it matched. <span style={{ opacity: .7 }}>API: {API_URL}</span></>} />

      <form className="searchbox" onSubmit={(e) => { e.preventDefault(); void run(q); }}>
        <Icon name="search" size={20} />
        <input className="grow" aria-label="Search people" placeholder="e.g. marine scientists in Kerala" value={q} onChange={(e) => setQ(e.target.value)} />
        <button type="submit" disabled={busy}>{busy ? "Searching…" : "Search"}</button>
      </form>
      <p style={{ marginTop: 16 }}>{EXAMPLES.map((x) => <button key={x} className="secondary chip-btn" type="button" onClick={() => { setQ(x); void run(x); }}>{x}</button>)}</p>
      {err && <p className="alert" role="alert"><Icon name="alert" size={18} /><span>{err}</span></p>}

      {res && (
        <div className="panel">
          <p className="muted" style={{ marginTop: 0 }}>{res.results.length} result{res.results.length === 1 ? "" : "s"} in {res.took_ms} ms{res.relaxed ? " (filters were relaxed to find matches)" : ""}</p>
          {res.results.length === 0 && <div className="empty"><h2>No one matches that yet.</h2><p>Try fewer words, or a place or a field.</p></div>}
          {res.results.map((h) => (
            <div key={h.id} className="hit">
              <Avatar name={h.full_name} tile={tileFor(h.sector || h.full_name)} />
              <div className="grow">
                <a href={`${WEB}/p/${h.slug}`} target="_blank" rel="noreferrer"><b>{h.full_name}</b></a> {h.is_demo && <span className="chip">demo</span>}
                <div className="muted">{[h.headline || h.sector, [h.city, h.state].filter(Boolean).join(", ")].filter(Boolean).join(" · ")}</div>
                <div style={{ marginTop: 6 }}>
                  {h.reasons.length ? h.reasons.map((r) => <span className="chip" key={r}>{r}</span>) : <Pill tone="quiet" icon="search">score {Math.round(h.score * 100)}</Pill>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <details className="panel" style={{ marginTop: 24 }}>
        <summary><Icon name="mail" /> Invite someone to get listed</summary>
        <p className="muted">For a specific notable person you know of. It creates a draft email with a link to start; you review and send it from <Link href="/followups">Follow-ups</Link>. People with an account or who opted out are refused.</p>
        <form onSubmit={invite}>
          <div className="row">
            <div className="grow"><label htmlFor="inv-name">Their name</label><input id="inv-name" required minLength={2} value={inv.name} onChange={(e) => setInv({ ...inv, name: e.target.value })} /></div>
            <div className="grow"><label htmlFor="inv-email">Their email</label><input id="inv-email" type="email" required value={inv.email} onChange={(e) => setInv({ ...inv, email: e.target.value })} /></div>
          </div>
          <label htmlFor="inv-note">A personal note (optional; links and contact details are removed)</label>
          <textarea id="inv-note" rows={3} maxLength={1500} value={inv.note} onChange={(e) => setInv({ ...inv, note: e.target.value })} />
          <p><button disabled={invBusy}>{invBusy ? "Drafting…" : "Create the draft"}</button></p>
          {invMsg && <p className="notice" role="status"><Icon name="check" size={18} /><span>{invMsg}</span></p>}
          {invErr && <p className="alert" role="alert"><Icon name="alert" size={18} /><span>{invErr}</span></p>}
        </form>
      </details>
    </main>
  );
}
