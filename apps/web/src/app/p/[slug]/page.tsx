import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BadgeCheck, ChevronRight, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SectorChip } from "@/components/directory/result-card";
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

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <nav aria-label="Breadcrumb" className="mb-6 flex items-center gap-1 text-sm text-muted-foreground">
        <Link href="/directory" className="hover:text-foreground">Registry</Link>
        <ChevronRight className="size-3.5" /> <span className="text-foreground">{p.full_name}</span>
      </nav>

      <div className="lg:grid lg:grid-cols-[22rem_minmax(0,1fr)] lg:items-start lg:gap-8">
      <header className="overflow-hidden rounded-3xl border border-border bg-card lg:sticky lg:top-20">
        <div className="relative h-24 overflow-hidden" style={{ background: `linear-gradient(120deg, ${color.ink}, ${color.primary})` }}>
          <SectorImage sector={p.sector} purpose="cover" width={900} creditAlign="right" className="absolute inset-0 size-full rounded-none opacity-90" />
        </div>
        <div className="px-6 pb-6">
          <div className="relative z-10 -mt-10 flex size-20 items-center justify-center rounded-full border-4 border-card font-display text-3xl font-semibold text-white" style={{ background: color.ink }} aria-hidden="true">
            {p.full_name.replace(/^(Dr\.?|Prof\.?|Adv\.?|Justice)\s+/i, "").charAt(0)}
          </div>
          <div className="mt-3 flex flex-col gap-3">
            <div>
              <h1 className="text-3xl font-semibold">{p.full_name}</h1>
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
            <p className={`inline-flex w-fit items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium ${sum.confirmed ? "bg-verified-soft text-verified" : "bg-muted text-muted-foreground"}`}>
              <BadgeCheck aria-hidden className="size-4" /> {sum.confirmed} of {sum.total} claims confirmed
            </p>
          </div>
          {p.bio && <BioProof bio={p.bio} claims={p.claims} />}
          {extras.length > 0 && (
            <dl className="mt-5 grid gap-x-8 gap-y-3 sm:grid-cols-2">
              {extras.map((d) => (
                <div key={d.key}>
                  <dt className="text-xs text-muted-foreground">{d.label}</dt>
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

      <div className="min-w-0">
      <section className="mt-8 lg:mt-0" aria-labelledby="ach">
        <h2 id="ach" className="text-2xl font-semibold">Achievements and the proof behind them</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {sum.confirmed} confirmed by a document, issuer or reviewer · {sum.web} backed by a public source · {sum.self} self-claimed.
          {decided ? ` ${decided}` : ""}
        </p>
        <ul className="mt-4 space-y-3">
          {claims.map((c) => (
            <ClaimCard key={c.id} claim={c} isDemo={p.is_demo} />
          ))}
        </ul>
      </section>

      {certs.length > 0 && (
        <section className="mt-8 rounded-2xl border border-border bg-card p-5" aria-labelledby="cert">
          <h2 id="cert" className="text-xl font-semibold">Signed certificate</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Cryptographically signed and recorded in the public transparency log. Anyone can check it, or try to forge it.
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
      </div>
    </div>
  );
}
