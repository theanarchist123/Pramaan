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
    <div className="mx-auto max-w-xl px-4 py-12">
      <span className="inline-flex size-11 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Sparkles />
      </span>
      <h1 className="mt-4 text-4xl font-semibold">{t("consent.title")}</h1>
      <p className="mt-2 text-lg text-muted-foreground">
        {t("consent.sub")}
      </p>

      <form
        className="mt-8 space-y-6 rounded-2xl border border-border bg-card p-6"
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
            className="h-11 text-base"
            autoComplete="name"
          />
          <p className="text-sm text-muted-foreground">
            {t("consent.nameHint")}
          </p>
        </div>

        <fieldset className="space-y-4">
          <legend className="mb-2 flex items-center gap-2 text-sm font-medium">
            <Lock className="size-4" /> {t("consent.legend")}
          </legend>
          <label className="flex cursor-pointer gap-3">
            <Checkbox checked={publicListing} onCheckedChange={(v) => setPublicListing(Boolean(v))} className="mt-0.5" />
            <span className="text-sm">
              <span className="font-medium">{t("consent.listingB")}</span>{" "}
              <span className="text-muted-foreground">{t("consent.listingR")}</span>
            </span>
          </label>
          <label className="flex cursor-pointer gap-3">
            <Checkbox checked={webResearch} onCheckedChange={(v) => setWebResearch(Boolean(v))} className="mt-0.5" />
            <span className="text-sm">
              <span className="font-medium inline-flex items-center gap-1"><Search className="size-3.5" /> {t("consent.researchB")}</span>{" "}
              <span className="text-muted-foreground">{t("consent.researchR")}</span>
            </span>
          </label>
        </fieldset>

        <Button type="submit" disabled={!publicListing || busy} className="h-11 w-full text-base">
          {busy ? t("consent.starting") : t("consent.start")}
        </Button>
      </form>
    </div>
  );
}
