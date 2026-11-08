"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ScanLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/lib/i18n";

export default function VerifyLookup() {
  const { t } = useI18n();
  const router = useRouter();
  const [code, setCode] = useState("");
  return (
    <div className="mx-auto max-w-xl px-4 py-16">
      <span className="inline-flex size-11 items-center justify-center rounded-full bg-indigo-soft text-indigo">
        <ScanLine />
      </span>
      <h1 className="mt-4 text-4xl font-semibold">{t("verify.title")}</h1>
      <p className="mt-2 text-muted-foreground">
        {t("verify.sub")}
      </p>
      <form
        className="mt-8 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (code.trim()) router.push(`/verify/${code.trim().toUpperCase()}`);
        }}
      >
        <label htmlFor="code" className="sr-only">{t("verify.codeLabel")}</label>
        <Input id="code" placeholder="PRM-XXXXXXXXXX" value={code} onChange={(e) => setCode(e.target.value)} className="h-11 font-mono text-base uppercase" />
        <Button type="submit" className="h-11 px-5">{t("verify.button")}</Button>
      </form>
    </div>
  );
}
