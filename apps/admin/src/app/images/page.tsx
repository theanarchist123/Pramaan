"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SECTORS } from "@pramaan/ui/sectors";
import { api, ApiError } from "@/lib/api";

interface Candidate {
  unsplash_id: string; url_raw: string; photographer_name: string; photographer_url: string; photo_url: string;
  download_location: string; alt_text: string; dominant_color: string; width: number; height: number; blur_hash: string;
}
interface Approved { id: string; sector: string; purpose: string; url_raw: string; alt: string; attribution: { photographer: string; photographer_url: string } }
type Purpose = "tile" | "cover" | "empty";

const UTM = "utm_source=pramaan&utm_medium=referral";
const thumb = (raw: string, w: number) => `${raw}${raw.includes("?") ? "&" : "?"}w=${w}&q=70&fm=webp&fit=crop&auto=format`;
const withUtm = (u: string) => `${u}${u.includes("?") ? "&" : "?"}${UTM}`;

/**
 * Curate the photographs the public site shows on field tiles, shelf headers and cover bands. A person looks at each candidate and approves it
 * one at a time (the Unsplash download endpoint is triggered at that moment, as their guidelines require). Nothing is imported in bulk, nothing
 * is downloaded or re-hosted: the public site hotlinks the photo from Unsplash and shows the photographer's credit. Never people.
 */
export default function ImagesPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [sector, setSector] = useState(SECTORS[0].name);
  const [purpose, setPurpose] = useState<Purpose>("tile");
  const [results, setResults] = useState<Candidate[] | null>(null);
  const [approved, setApproved] = useState<Approved[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const loadApproved = useCallback(async () => {
    try {
      setApproved(await api<Approved[]>(`/v1/images/sector/${encodeURIComponent(sector)}`));
    } catch {
      setApproved([]);
    }
  }, [sector]);
  useEffect(() => { void loadApproved(); }, [loadApproved]);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setMsg("");
    try {
      setResults(await api<Candidate[]>(`/v1/admin/images/candidates?q=${encodeURIComponent(q)}`));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) router.push("/login");
      else if (err instanceof ApiError && err.status === 503)
        setError("Unsplash is not connected. Register a free application at unsplash.com/developers, put its access key in the backend .env as UNSPLASH_ACCESS_KEY, then restart the API. Until then the public site shows a colour pattern instead of photographs.");
      else setError(err instanceof Error ? err.message : "Search failed");
      setResults(null);
    } finally {
      setBusy(false);
    }
  }

  async function approve(c: Candidate) {
    setError(""); setMsg("");
    try {
      await api("/v1/admin/images/approve", { method: "POST", json: { candidate: c, sector, purpose } });
      setMsg(`Approved for ${sector} (${purpose}). It now appears on the public site.`);
      await loadApproved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't approve");
    }
  }

  async function remove(id: string) {
    try {
      await api(`/v1/admin/images/${id}/deactivate`, { method: "POST" });
      await loadApproved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't remove");
    }
  }

  return (
    <main>
      <div className="row"><Link href="/">Queue</Link><h1 className="grow">Photographs</h1></div>
      <p className="muted">Search Unsplash, look at each photo, and approve the ones that suit a field. Landscapes, objects, textures, buildings: never a photograph of a person.</p>

      <form className="panel" onSubmit={search}>
        <div className="row">
          <div className="grow"><label htmlFor="q">Search Unsplash</label><input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. wind turbines at dawn" minLength={2} required /></div>
          <label className="inline">Approve into
            <select value={sector} onChange={(e) => setSector(e.target.value)}>{SECTORS.map((s) => <option key={s.slug}>{s.name}</option>)}</select>
          </label>
          <label className="inline">As
            <select value={purpose} onChange={(e) => setPurpose(e.target.value as Purpose)}>
              <option value="tile">Field tile</option><option value="cover">Cover band</option><option value="empty">Empty state</option>
            </select>
          </label>
          <button disabled={busy}>{busy ? "Searching..." : "Search"}</button>
        </div>
        {error && <p className="err" role="alert">{error}</p>}
        {msg && <p role="status">{msg}</p>}
      </form>

      {results && (
        <section className="panel" aria-label="Candidates">
          <strong>{results.length} candidates</strong>
          {results.length === 0 && <p className="muted">Nothing found. Try a different search.</p>}
          <ul className="photos">
            {results.map((c) => (
              <li key={c.unsplash_id}>
                {/* eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose (Unsplash API terms) */}
                <img src={thumb(c.url_raw, 420)} alt={c.alt_text || "Candidate photograph"} loading="lazy" style={{ backgroundColor: c.dominant_color || undefined }} />
                <div className="muted">
                  Photo by <a href={withUtm(c.photographer_url)} target="_blank" rel="noopener noreferrer">{c.photographer_name}</a> on{" "}
                  <a href={withUtm("https://unsplash.com/")} target="_blank" rel="noopener noreferrer">Unsplash</a>
                </div>
                <button onClick={() => approve(c)} aria-label={`Approve this photo by ${c.photographer_name} for ${sector}`}>Approve for {sector}</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="panel" aria-label="Approved photographs">
        <strong>Approved for {sector}</strong>
        {approved.length === 0 ? <p className="muted">None yet. The public site shows a colour pattern for this field until you approve a photo.</p> : (
          <ul className="photos">
            {approved.map((a) => (
              <li key={a.id}>
                {/* eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose (Unsplash API terms) */}
                <img src={thumb(a.url_raw, 420)} alt={a.alt} loading="lazy" />
                <div className="muted">{a.purpose} · Photo by {a.attribution.photographer}</div>
                <button className="secondary" onClick={() => remove(a.id)}>Remove</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
