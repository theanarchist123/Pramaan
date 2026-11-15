import { ShareRow } from "@/components/share-row";
import { IntroRequest } from "@/components/profile/intro-request";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BadgeCheck, ChevronRight, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, initialsOf, tileOf } from "@/components/profile/avatar";
import { BioProof } from "@/components/profile/bio-proof";
import { ClaimCard } from "@/components/profile/claim-card";
import { SectorImage } from "@/components/sector-image";
import { decisionLine, summarise } from "@/lib/claim-summary";
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
  const verified = summarise(p.claims).confirmed;
  return {
    title: p.full_name,
    description: `${p.headline || p.sector}${p.state ? ` · ${p.state}` : ""} — ${verified} achievement${verified === 1 ? "" : "s"} confirmed by evidence on Pramaan.`,
  };
}

export default async function PublicProfile({ params }: { params: Promise<{ slug: string }> }) {
  const data = await load((await params).slug);
  if (!data) notFound();
  const { profile: p, certs } = data;
  const defs = await loadFields();
  const extras = defs.filter((d) => p.custom?.[d.key] != null && p.custom[d.key] !== "");
  const color = paletteFor(p.sector);
  const sum = summarise(p.claims);
  const decided = decisionLine(p);
  const order = { issuer: 0, document: 1, human: 2, web: 3, self: 4 } as const;
  const claims = [...p.claims].sort((a, b) => order[a.status] - order[b.status]);

  const tile = tileOf(p.full_name);
  const verifiedTotal = sum.confirmed;
  return (
    <div className="md:-mt-16">
      {/* Cover: this person's own colour, a big avatar and their name set large. */}
      <section className="relative overflow-hidden" style={{ background: `var(--tile${tile})`, color: `var(--tile${tile}i)` }}>
        <span aria-hidden className="pointer-events-none absolute -right-6 -top-10 select-none font-display text-[22rem] font-extrabold leading-none opacity-[0.12]">{initialsOf(p.full_name).slice(0, 1)}</span>
        <div className="relative mx-auto max-w-6xl px-4 pb-24 pt-8 md:pt-28">
          <nav aria-label="Breadcrumb" className="mb-6 flex items-center gap-1 text-sm font-semibold">
            <Link href="/directory" className="hover:underline">Registry</Link>
            <ChevronRight className="size-3.5" /> <span>{p.full_name}</span>
          </nav>
          <div className="flex flex-wrap items-end gap-6">
            <Avatar name={p.full_name} photo={p.photo_url} verified={p.status === "approved"} className="size-28 rounded-[2rem] border-4 border-current text-5xl md:size-36 md:text-6xl" />
            <div className="min-w-0 flex-1">
              <h1 className="text-balance text-5xl leading-[1] md:text-7xl">{p.full_name}</h1>
              {p.headline && <p className="mt-3 max-w-2xl text-xl font-medium md:text-2xl">{p.headline}</p>}
              <div className="mt-4 flex flex-wrap items-center gap-2 text-sm font-semibold">
                <span className="rounded-full border-2 border-current px-3 py-1">{p.sector}</span>
                {p.state && (
                  <span className="inline-flex items-center gap-1 rounded-full border-2 border-current px-3 py-1"><MapPin className="size-3.5" /> {[p.city, p.state].filter(Boolean).join(", ")}</span>
                )}
                {p.is_demo && <span className="rounded-full border-2 border-current px-3 py-1">Fictional demo profile</span>}
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="relative z-10 mx-auto -mt-12 max-w-6xl px-4 pb-16">
        <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_21rem] lg:items-start lg:gap-8">
          <div className="min-w-0 space-y-8">
            {p.bio && (
              <section aria-label="About" className="rounded-[1.8rem] border border-border bg-card p-6 shadow-[var(--lift-1)]">
                <h2 className="text-2xl">About</h2>
                <BioProof bio={p.bio} claims={p.claims} />
              </section>
            )}

            <section aria-labelledby="ach">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <h2 id="ach" className="text-3xl md:text-4xl">Proven achievements</h2>
                <p className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-bold ${verifiedTotal ? "bg-[var(--verified)] text-[var(--bond)]" : "bg-muted text-muted-foreground"}`}>
                  <BadgeCheck aria-hidden className="size-4" /> {sum.confirmed} of {sum.total} claims confirmed
                </p>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {sum.confirmed} confirmed by a document, issuer or reviewer · {sum.web} backed by a public source · {sum.self} self-claimed.
                {decided ? ` ${decided}` : ""}
              </p>
              <ul className="mt-5 space-y-3">
                {claims.map((c) => (
                  <ClaimCard key={c.id} claim={c} isDemo={p.is_demo} />
                ))}
              </ul>
            </section>
          </div>

          <aside className="mt-8 min-w-0 space-y-5 lg:sticky lg:top-24 lg:mt-0">
            {certs.length > 0 && (
              <section aria-labelledby="cert" className="pop rounded-3xl bg-card p-5">
                <h2 id="cert" className="text-2xl">Signed certificate</h2>
                <p className="mt-1 text-sm text-muted-foreground">Signed and recorded in the public log. Anyone can check it, or try to forge it.</p>
                <div className="mt-3 flex flex-col gap-2">
                  {certs.map((c) => (
                    <Button key={c.code} size="lg" render={<Link href={`/verify/${c.code}`} />} nativeButton={false}>
                      <BadgeCheck /> Check {c.code}
                    </Button>
                  ))}
                </div>
              </section>
            )}

            <section aria-label="Share" className="rounded-3xl border border-border bg-card p-5">
              <h2 className="text-xl">Share this profile</h2>
              <ShareRow className="mt-3" text={`${p.full_name}: ${p.headline || p.sector}. See how each achievement was checked.`} />
            </section>

            <IntroRequest slug={p.slug} name={p.full_name} />

            <section aria-label="At a glance" className="overflow-hidden rounded-3xl border border-border bg-card">
              <div className="relative h-24 overflow-hidden" style={{ background: `linear-gradient(120deg, ${color.ink}, ${color.primary})` }}>
                <SectorImage sector={p.sector} purpose="cover" width={900} creditAlign="right" className="absolute inset-0 size-full rounded-none opacity-90" />
              </div>
              <div className="p-5">
                <h2 className="text-xl">At a glance</h2>
                <dl className="mt-3 space-y-3 text-sm">
                  <div><dt className="text-muted-foreground">Field</dt><dd className="font-semibold">{p.sector}</dd></div>
                  {p.state && <div><dt className="text-muted-foreground">Based in</dt><dd className="font-semibold">{[p.city, p.state].filter(Boolean).join(", ")}</dd></div>}
                  {p.institutions.length > 0 && <div><dt className="text-muted-foreground">Associated with</dt><dd className="font-semibold">{p.institutions.join(" · ")}</dd></div>}
                  {extras.map((d) => (
                    <div key={d.key}>
                      <dt className="text-muted-foreground">{d.label}</dt>
                      <dd className="font-semibold">
                        {d.type === "url" ? <a href={String(p.custom[d.key])} target="_blank" rel="noreferrer noopener nofollow" className="underline">{String(p.custom[d.key])}</a> : show(p.custom[d.key])}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
