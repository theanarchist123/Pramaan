"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, BookOpen, Briefcase, FlaskConical, HeartPulse, Landmark, Leaf, Megaphone, Palette, Scale, Trophy, Users, Zap, Cpu, HandHeart } from "lucide-react";
import { PersonCard, type PersonSummary } from "@/components/profile/person-card";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const FIELD_ICONS: Record<string, typeof Zap> = {
  Energy: Zap, Science: FlaskConical, Healthcare: HeartPulse, Sports: Trophy, Agriculture: Leaf, Media: Megaphone,
  "Arts & Culture": Palette, Education: BookOpen, Literature: BookOpen, Technology: Cpu, Business: Briefcase,
  "Public Service": Landmark, Law: Scale, "Social Work": HandHeart, Other: Users,
};

/** The home page shows people first. Only profiles with a headline are featured (a card needs something to say). */
export function PeopleAndFields() {
  const { t } = useI18n();
  const [all, setAll] = useState<PersonSummary[] | null>(null);

  useEffect(() => {
    api<PersonSummary[]>("/v1/profiles?limit=100", { auth: false }).then(setAll).catch(() => setAll([]));
  }, []);

  const featured = useMemo(() => (all ?? []).filter((p) => p.headline.trim()).slice(0, 8), [all]);
  const fields = useMemo(() => {
    const counts: Record<string, number> = {};
    (all ?? []).forEach((p) => (counts[p.sector] = (counts[p.sector] ?? 0) + 1));
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [all]);

  return (
    <>
      <section id="people" className="mx-auto max-w-7xl px-4 py-14" aria-labelledby="people-h">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="people-h" className="text-3xl md:text-5xl">{t("h2.peopleH")}</h2>
            <p className="mt-2 max-w-xl text-muted-foreground">{t("h2.peopleP")}</p>
          </div>
          <Link href="/directory" className="inline-flex items-center gap-1 border-b-2 border-[var(--brand)] font-semibold">
            {t("h2.seeAll")} <ArrowRight className="size-4" />
          </Link>
        </div>
        {all === null ? (
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => <div key={i} className="h-36 animate-pulse rounded-[1.4rem] bg-muted" />)}
          </div>
        ) : featured.length === 0 ? (
          <p className="mt-6 rounded-3xl border-2 border-dashed border-border p-8 text-center text-muted-foreground">{t("h2.noPeople")}</p>
        ) : (
          <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {featured.map((p) => (
              <li key={p.slug}><PersonCard p={p} /></li>
            ))}
          </ul>
        )}
      </section>

      {fields.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pb-14" aria-labelledby="fields-h">
          <h2 id="fields-h" className="text-3xl md:text-5xl">{t("h2.fieldsH")}</h2>
          <p className="mt-2 text-muted-foreground">{t("h2.fieldsP")}</p>
          <ul className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {fields.slice(0, 10).map(([name, n], i) => {
              const Icon = FIELD_ICONS[name] ?? Users;
              const k = (i % 6) + 1;
              return (
                <li key={name}>
                  <Link
                    href={`/directory?sector=${encodeURIComponent(name)}`}
                    className="flex min-h-28 flex-col justify-between rounded-[1.3rem] p-4 transition-transform hover:-translate-y-1 hover:-rotate-1"
                    style={{ background: `var(--tile${k})`, color: `var(--tile${k}i)` }}
                  >
                    <Icon aria-hidden className="size-6" />
                    <span>
                      <span className="block font-display text-lg font-bold leading-tight">{name}</span>
                      <span className="text-sm font-semibold">{n} {n === 1 ? t("h2.person") : t("h2.people")}</span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </>
  );
}
