"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Search } from "lucide-react";
import { HandUnderline } from "@/components/landing/hand-underline";
import { LiveDemo } from "@/components/landing/live-demo";
import { useI18n, type Key } from "@/lib/i18n";

const EXAMPLES: { q: string; key: Key }[] = [
  { q: "clean-energy researchers in Karnataka", key: "h2.ex1" },
  { q: "teaches classical dance to children", key: "h2.ex2" },
  { q: "journalists investigating river pollution", key: "h2.ex3" },
  { q: "gold medal athletes", key: "h2.ex4" },
];

export function Hero() {
  const { t } = useI18n();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [ph, setPh] = useState(0);

  // The placeholder cycles through real example questions (a typewriter would fight screen readers and Devanagari, so it just swaps).
  useEffect(() => {
    const id = window.setInterval(() => setPh((i) => (i + 1) % EXAMPLES.length), 3200);
    return () => window.clearInterval(id);
  }, []);

  const go = (text: string) => router.push(`/directory?q=${encodeURIComponent(text.trim())}`);

  return (
    <section data-nav-tone="on-light" className="relative overflow-hidden bg-[var(--brand)] text-[var(--on-brand)]">
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 pb-16 pt-8 md:pb-20 md:pt-24 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <div className="min-w-0">
          <h1 className="text-balance text-5xl leading-[1.02] md:text-6xl xl:text-7xl">
            {t("h2.h1a")} <HandUnderline>{t("h2.h1b")}</HandUnderline>
          </h1>
          <p className="mt-6 max-w-xl text-lg text-[#3B2E00]">{t("h2.lead")}</p>

          <form
            role="search"
            className="mt-8 flex max-w-2xl rounded-full border-2 border-[#14152B] bg-white p-1.5 shadow-[0_6px_0_#14152B]"
            onSubmit={(e) => {
              e.preventDefault();
              go(q || t(EXAMPLES[ph].key));
            }}
          >
            <label htmlFor="hero-q" className="sr-only">{t("h2.searchLabel")}</label>
            <Search aria-hidden className="ml-4 hidden size-5 self-center text-[#4B4E68] sm:block" />
            <input
              id="hero-q"
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t(EXAMPLES[ph].key)}
              className="min-w-0 flex-1 bg-transparent px-4 py-3 text-base text-[#14152B] placeholder:text-[#5E6280] focus:outline-none"
              autoComplete="off"
            />
            <button type="submit" className="rounded-full bg-[#14152B] px-6 text-base font-semibold text-white hover:bg-[#24264A]">
              {t("dir.searchBtn")}
            </button>
          </form>

          <div className="mt-4 flex flex-wrap gap-2" aria-label={t("h2.examples")}>
            {EXAMPLES.map((e) => (
              <button
                key={e.q}
                type="button"
                onClick={() => go(e.q)}
                className="rounded-full border border-[#14152B]/30 bg-white/55 px-3.5 py-1.5 text-sm font-medium hover:bg-white"
              >
                {t(e.key)}
              </button>
            ))}
          </div>

          <div className="mt-9 flex flex-wrap items-center gap-x-5 gap-y-3">
            <Link
              href="/onboard"
              className="inline-flex h-12 items-center gap-2 rounded-full bg-[#14152B] px-6 text-base font-semibold text-white transition-transform hover:-translate-y-0.5 hover:shadow-[0_5px_0_rgb(20_21_43/0.25)]"
            >
              {t("h2.cta")} <ArrowRight className="size-5" />
            </Link>
            <span className="text-sm text-[#3B2E00]">{t("h2.ctaNote")}</span>
          </div>
        </div>

        <div className="min-w-0">
          <LiveDemo />
        </div>
      </div>
    </section>
  );
}
