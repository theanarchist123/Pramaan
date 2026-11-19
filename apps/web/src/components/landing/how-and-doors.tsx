"use client";

import Link from "next/link";
import { ArrowRight, QrCode } from "lucide-react";
import { useI18n, type Key } from "@/lib/i18n";

const STEPS: { n: number; title: Key; body: Key }[] = [
  { n: 1, title: "h2.s1t", body: "h2.s1b" },
  { n: 2, title: "h2.s2t", body: "h2.s2b" },
  { n: 3, title: "h2.s3t", body: "h2.s3b" },
];

export function HowAndDoors() {
  const { t } = useI18n();
  return (
    <>
      <section id="how" className="bg-[var(--stamp-tint)]">
        <div className="mx-auto max-w-7xl px-4 py-16">
          <h2 className="text-3xl md:text-5xl">{t("h2.howH")}</h2>
          <p className="mt-2 text-muted-foreground">{t("h2.howP")}</p>
          <ol className="mt-8 grid gap-5 md:grid-cols-3">
            {STEPS.map((s) => (
              <li key={s.n} className="pop rounded-3xl bg-card p-6">
                <span className="mb-4 flex size-10 items-center justify-center rounded-xl bg-[var(--brand)] font-display text-xl font-extrabold text-[var(--on-brand)]">{s.n}</span>
                <h3 className="text-2xl">{t(s.title)}</h3>
                <p className="mt-1.5 text-muted-foreground">{t(s.body)}</p>
              </li>
            ))}
          </ol>
          <Link href="/onboard" className="mt-8 inline-flex h-12 items-center gap-2 rounded-full bg-primary px-6 font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5">
            {t("h2.startCta")} <ArrowRight className="size-5" />
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16">
        <div className="grid gap-5 md:grid-cols-2">
          <div className="flex flex-col items-start gap-3 rounded-[1.8rem] bg-[var(--brand)] p-8 text-[var(--on-brand)]" data-nav-tone="on-light">
            <h3 className="text-3xl md:text-4xl">{t("h2.d1h")}</h3>
            <p className="max-w-md">{t("h2.d1p")}</p>
            <Link href="/onboard" className="mt-2 inline-flex h-11 items-center rounded-full bg-[#14152B] px-6 font-semibold text-white">{t("h2.d1c")}</Link>
          </div>
          <div className="flex flex-col items-start gap-3 rounded-[1.8rem] bg-[var(--tile1)] p-8 text-[var(--tile1i)]">
            <h3 className="text-3xl md:text-4xl">{t("h2.d2h")}</h3>
            <p className="max-w-md">{t("h2.d2p")}</p>
            <Link href="/directory" className="mt-2 inline-flex h-11 items-center rounded-full bg-[var(--tile1i)] px-6 font-semibold text-[var(--tile1)]">{t("h2.d2c")}</Link>
          </div>
        </div>
      </section>

      <section className="border-t border-border">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-6 px-4 py-12">
          <span className="flex size-20 items-center justify-center rounded-2xl border-2 border-foreground"><QrCode aria-hidden className="size-10" /></span>
          <div className="min-w-0 flex-[1_1_16rem]">
            <h3 className="text-2xl md:text-3xl">{t("h2.trustH")}</h3>
            <p className="mt-1 max-w-2xl text-muted-foreground">{t("h2.trustP")}</p>
          </div>
          <Link href="/verify" className="inline-flex h-11 items-center rounded-full border-2 border-foreground px-6 font-semibold">{t("h2.trustC")}</Link>
        </div>
      </section>

      <footer className="mx-auto flex max-w-7xl flex-wrap justify-between gap-3 px-4 pb-10 text-sm text-muted-foreground">
        <span>{t("h2.footer")}</span>
        <span className="flex gap-4">
          <Link href="/how-we-check" className="hover:text-foreground">How we check</Link>
          <Link href="/transparency" className="hover:text-foreground">{t("nav.transparency")}</Link>
          <Link href="/developers" className="hover:text-foreground">{t("nav.developers")}</Link>
        </span>
      </footer>
    </>
  );
}
