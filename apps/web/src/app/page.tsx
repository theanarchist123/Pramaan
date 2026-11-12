"use client";

import Link from "next/link";
import { ArrowRight, BadgeCheck, FileSearch, MessagesSquare, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LandingStats } from "@/components/landing/stats";
import { AgentRoster } from "@/components/landing/agent-roster";
import { LedgerStrip } from "@/components/landing/ledger-strip";
import { DeskCertificate } from "@/components/landing/desk-certificate";
import { ProofTable } from "@/components/landing/proof-table";
import { SectorBento } from "@/components/landing/sector-bento";
import { useI18n, type Key } from "@/lib/i18n";

const STEPS: { icon: typeof BadgeCheck; title: Key; body: Key }[] = [
  { icon: MessagesSquare, title: "home.s1t", body: "home.s1b" },
  { icon: FileSearch, title: "home.s2t", body: "home.s2b" },
  { icon: ShieldCheck, title: "home.s3t", body: "home.s3b" },
  { icon: BadgeCheck, title: "home.s4t", body: "home.s4b" },
];

export default function Home() {
  const { t } = useI18n();
  return (
    <>
      <section className="paper-glow border-b border-border">
        <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-12 md:py-20 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          <div className="min-w-0">
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
              <span className="size-1.5 rounded-full bg-verified" /> {t("home.badge")}
            </p>
            <h1 className="text-balance text-5xl leading-[1.02] font-semibold tracking-tight md:text-6xl xl:text-7xl">
              {t("home.h1a")}
              <br />
              <span className="text-primary">{t("home.h1b")}</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg text-muted-foreground">{t("home.lead")}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" className="h-11 px-5 text-base" render={<Link href="/onboard" />} nativeButton={false}>
                {t("home.cta1")} <ArrowRight />
              </Button>
              <Button size="lg" variant="outline" className="h-11 px-5 text-base" render={<Link href="/verify" />} nativeButton={false}>
                {t("home.cta2")}
              </Button>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">{t("home.hint")}</p>
            <LandingStats />
          </div>
          <div className="min-w-0">
            <DeskCertificate />
          </div>
        </div>
      </section>

      <LedgerStrip />

      <section className="mx-auto max-w-7xl px-4 py-14" aria-labelledby="browse-h">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="browse-h" className="text-balance text-3xl font-semibold md:text-4xl">Browse by field</h2>
            <p className="mt-1 max-w-xl text-muted-foreground">Fourteen fields, each with the people whose achievements have been checked. Pick one to see its shelf.</p>
          </div>
          <Button variant="outline" render={<Link href="/directory" />} nativeButton={false}>Open the registry <ArrowRight /></Button>
        </div>
        <div className="mt-6"><SectorBento /></div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16">
        <h2 className="text-balance text-3xl font-semibold md:text-4xl">{t("home.how")}</h2>
        <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.title} className="rounded-[var(--radius-panel)] border border-border border-t-[3px] border-t-primary bg-card p-5 shadow-[var(--lift-1)]">
              <div className="flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <s.icon className="size-4.5" />
                </span>
                <span className="text-xs text-muted-foreground">
                  {t("home.step")} {i + 1}
                </span>
              </div>
              <h3 className="mt-4 text-lg font-semibold">{t(s.title)}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{t(s.body)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mx-auto grid max-w-7xl items-center gap-8 px-4 py-16 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]" aria-labelledby="checks-h">
        <div>
          <h2 id="checks-h" className="text-balance text-3xl font-semibold md:text-4xl">What a check really does</h2>
          <p className="mt-2 max-w-md text-muted-foreground">Verifying a certificate is four small, honest steps. This one ran when the page loaded, against the newest certificate in the registry.</p>
        </div>
        <div className="min-w-0">
          <ProofTable />
        </div>
      </section>

      <section className="border-y border-border bg-card/50">
        <div className="mx-auto max-w-7xl px-4 py-16">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-3xl font-semibold">{t("home.teamH")}</h2>
              <p className="mt-2 max-w-2xl text-muted-foreground">{t("home.teamP")}</p>
            </div>
            <Button variant="outline" render={<Link href="/mission-control" />} nativeButton={false}>
              {t("home.openMission")} <ArrowRight />
            </Button>
          </div>
          <AgentRoster />
        </div>
      </section>

      <footer className="mx-auto max-w-7xl px-4 py-10 text-sm text-muted-foreground">{t("home.footer")}</footer>
    </>
  );
}
