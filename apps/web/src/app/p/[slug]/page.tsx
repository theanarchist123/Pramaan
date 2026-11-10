import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BadgeCheck, ChevronRight, MapPin, Quote } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SectorChip } from "@/components/directory/result-card";
import { VerificationBadge } from "@/components/verification-badge";
import { API_URL } from "@/lib/api";
import { paletteFor } from "@/lib/certificate-art";
import type { Profile } from "@/lib/types";

interface FieldDef { key: string; label: string; type: string }

async function loadFields(): Promise<FieldDef[]> {
  return fetch(`${API_URL}/v1/fields`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : [])).catch(() => []);
}

function show(v: unknown): string {
  return Array.isArray(v) ? v.join(", ") : String(v);
}

async function load(slug: string): Promise<{ profile: Profile; certs: { code: string; issued_at: string }[] } | null> {
  const res = await fetch(`${API_URL}/v1/profiles/${encodeURIComponent(slug)}`, { cache: "no-store" }).catch(() => null);
  if (!res || !res.ok) return null;
  const profile = (await res.json()) as Profile;
  const certs = await fetch(`${API_URL}/v1/public/${encodeURIComponent(slug)}/certificates`, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : []))
    .catch(() => []);
  return { profile, certs };
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const data = await load((await params).slug);
  if (!data) return { title: "Profile not found" };
  const { profile: p } = data;
  const verified = p.claims.filter((c) => c.status !== "self").length;
  return {
    title: p.full_name,
    description: `${p.headline || p.sector}${p.state ? ` · ${p.state}` : ""} — ${verified} achievement${verified === 1 ? "" : "s"} checked against evidence on Pramaan.`,
  };
}

export default async function PublicProfile({ params }: { params: Promise<{ slug: string }> }) {
  const data = await load((await params).slug);
  if (!data) notFound();
  const { profile: p, certs } = data;
  const defs = await loadFields();
  const extras = defs.filter((d) => p.custom?.[d.key] != null && p.custom[d.key] !== "");
  const color = paletteFor(p.sector);
  const verified = p.claims.filter((c) => c.status !== "self");
  const order = { issuer: 0, document: 1, human: 2, web: 3, self: 4 } as const;
  const claims = [...p.claims].sort((a, b) => order[a.status] - order[b.status]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <nav aria-label="Breadcrumb" className="mb-6 flex items-center gap-1 text-sm text-muted-foreground">
        <Link href="/directory" className="hover:text-foreground">Registry</Link>
        <ChevronRight className="size-3.5" /> <span className="text-foreground">{p.full_name}</span>
      </nav>

      <header className="overflow-hidden rounded-3xl border border-border bg-card">
        <div className="h-24" style={{ background: `linear-gradient(120deg, ${color.ink}, ${color.primary})` }} />
        <div className="px-6 pb-6">
          <div className="-mt-10 flex size-20 items-center justify-center rounded-full border-4 border-card font-display text-3xl font-semibold text-white" style={{ background: color.ink }} aria-hidden="true">
            {p.full_name.replace(/^(Dr\.?|Prof\.?|Adv\.?|Justice)\s+/i, "").charAt(0)}
          </div>
          <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-4xl font-semibold">{p.full_name}</h1>
              <p className="mt-1 text-lg text-muted-foreground">{p.headline}</p>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <SectorChip sector={p.sector} />
                {p.state && (
                  <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
                    <MapPin className="size-3.5" /> {[p.city, p.state].filter(Boolean).join(", ")}
                  </span>
                )}
                {p.is_demo && <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">Fictional demo profile</span>}
              </div>
            </div>
            <p className="inline-flex items-center gap-1.5 rounded-full bg-verified-soft px-3 py-1.5 text-sm font-medium text-verified">
              <BadgeCheck className="size-4" /> {verified.length} of {p.claims.length} claims verified
            </p>
          </div>
          {p.bio && <p className="mt-5 max-w-2xl text-[17px] leading-relaxed">{p.bio}</p>}
          {extras.length > 0 && (
            <dl className="mt-5 grid gap-x-8 gap-y-3 sm:grid-cols-2">
              {extras.map((d) => (
                <div key={d.key}>
                  <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{d.label}</dt>
                  <dd className="text-[15px]">
                    {d.type === "url" ? <a href={String(p.custom[d.key])} target="_blank" rel="noreferrer noopener nofollow" className="text-primary underline">{String(p.custom[d.key])}</a> : show(p.custom[d.key])}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {p.institutions.length > 0 && (
            <p className="mt-4 text-sm text-muted-foreground">
              Associated with {p.institutions.join(" · ")}
            </p>
          )}
        </div>
      </header>

      <section className="mt-8" aria-labelledby="ach">
        <h2 id="ach" className="text-2xl font-semibold">Achievements & the proof behind them</h2>
        <ul className="mt-4 space-y-3">
          {claims.map((c) => (
            <li key={c.id} className="rounded-2xl border border-border bg-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                    {c.field}{c.year ? ` · ${c.year}` : ""}
                  </p>
                  <p className="mt-0.5">{c.value}</p>
                </div>
                <VerificationBadge status={c.status} className="shrink-0" />
              </div>
              {c.evidence.filter((e) => e.kind !== "chat").length > 0 && (
                <details className="mt-3 text-sm">
                  <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Show the evidence</summary>
                  <ul className="mt-2 space-y-2">
                    {c.evidence.filter((e) => e.kind !== "chat").map((e) => (
                      <li key={e.id} className="rounded-xl bg-muted/60 p-3">
                        <p className="flex gap-2 italic"><Quote className="mt-0.5 size-3.5 shrink-0 opacity-60" /> {e.quote}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {e.kind === "document" ? "From an uploaded credential" : "From a public source"}
                          {e.url && !p.is_demo && (
                            <> · <a href={e.url} target="_blank" rel="noreferrer" className="underline">open source</a></>
                          )}
                        </p>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          ))}
        </ul>
      </section>

      {certs.length > 0 && (
        <section className="mt-8 rounded-2xl border border-border bg-card p-5" aria-labelledby="cert">
          <h2 id="cert" className="text-xl font-semibold">Signed certificate</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Cryptographically signed and recorded in the public transparency log. Anyone can verify it — or try to forge it.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {certs.map((c) => (
              <Button key={c.code} variant="outline" render={<Link href={`/verify/${c.code}`} />} nativeButton={false}>
                <BadgeCheck /> Verify {c.code}
              </Button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
