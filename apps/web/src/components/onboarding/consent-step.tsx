"use client";

import { useState } from "react";
import { Lock, Search, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/lib/i18n";

export interface ConsentChoice {
  name: string;
  publicListing: boolean;
  webResearch: boolean;
}

export function ConsentStep({ busy, onStart }: { busy: boolean; onStart: (c: ConsentChoice) => void }) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [publicListing, setPublicListing] = useState(false);
  const [webResearch, setWebResearch] = useState(true);

  return (
    <div className="-mt-28 md:-mt-16">
      <section data-nav-tone="on-light" className="bg-[var(--brand)] text-[var(--on-brand)]">
        <div className="mx-auto max-w-5xl px-4 pb-24 pt-36 md:pt-28">
          <span className="inline-flex size-12 items-center justify-center rounded-2xl bg-[#14152B] text-[var(--brand)]"><Sparkles /></span>
          <h1 className="mt-4 max-w-3xl text-balance text-5xl leading-[1.02] md:text-7xl">{t("consent.title")}</h1>
          <p className="mt-4 max-w-2xl text-lg text-[#3B2E00]">{t("consent.sub")}</p>
        </div>
      </section>

      <div className="relative z-10 mx-auto -mt-14 grid max-w-5xl gap-6 px-4 pb-16 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <form
          className="pop space-y-6 rounded-[1.8rem] bg-card p-6"
          onSubmit={(e) => {
            e.preventDefault();
            onStart({ name: name.trim(), publicListing, webResearch });
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="start-name" className="text-base">{t("consent.nameLabel")} <span className="text-muted-foreground">{t("consent.optional")}</span></Label>
            <Input
              id="start-name"
              placeholder="e.g. Dr. Meera Iyer"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-12 rounded-2xl text-base"
              autoComplete="name"
            />
            <p className="text-sm text-muted-foreground">{t("consent.nameHint")}</p>
          </div>

          <fieldset className="space-y-4">
            <legend className="mb-2 flex items-center gap-2 text-sm font-bold">
              <Lock className="size-4" /> {t("consent.legend")}
            </legend>
            <label className="flex cursor-pointer gap-3 rounded-2xl border border-border p-3">
              <Checkbox checked={publicListing} onCheckedChange={(v) => setPublicListing(Boolean(v))} className="mt-0.5" />
              <span className="text-sm">
                <span className="font-semibold">{t("consent.listingB")}</span>{" "}
                <span className="text-muted-foreground">{t("consent.listingR")}</span>
              </span>
            </label>
            <label className="flex cursor-pointer gap-3 rounded-2xl border border-border p-3">
              <Checkbox checked={webResearch} onCheckedChange={(v) => setWebResearch(Boolean(v))} className="mt-0.5" />
              <span className="text-sm">
                <span className="inline-flex items-center gap-1 font-semibold"><Search className="size-3.5" /> {t("consent.researchB")}</span>{" "}
                <span className="text-muted-foreground">{t("consent.researchR")}</span>
              </span>
            </label>
          </fieldset>

          <Button type="submit" disabled={!publicListing || busy} size="lg" className="w-full">
            {busy ? t("consent.starting") : t("consent.start")}
          </Button>
        </form>

        <aside aria-label="What happens next" className="space-y-3 lg:pt-6">
          <h2 className="text-2xl">What happens next</h2>
          {[
            ["Chat", "Saathi asks a few friendly questions. Speak or type, in any language."],
            ["Check", "Add a document if you have one. We match it to what you said."],
            ["Share", "Get a certificate with a QR code. You choose what's public."],
          ].map(([h, d], i) => (
            <div key={h} className="flex gap-3 rounded-2xl border border-border bg-card p-4">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-xl font-display text-lg font-extrabold" style={{ background: `var(--tile${i + 1})`, color: `var(--tile${i + 1}i)` }}>{i + 1}</span>
              <p className="text-sm"><b className="block text-base">{h}</b><span className="text-muted-foreground">{d}</span></p>
            </div>
          ))}
        </aside>
      </div>
    </div>
  );
}
