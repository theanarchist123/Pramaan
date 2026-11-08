"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export function LandingStats() {
  const { t } = useI18n();
  const [stats, setStats] = useState<{ profiles: number; certificates: number } | null>(null);
  useEffect(() => {
    api<{ profiles: number; certificates: number }>("/v1/stats", { auth: false }).then(setStats).catch(() => {});
  }, []);
  if (!stats || (stats.profiles === 0 && stats.certificates === 0)) return null;
  return (
    <dl className="mt-10 flex gap-8">
      <div>
        <dt className="text-xs text-muted-foreground">{t("home.verifiedProfiles")}</dt>
        <dd className="font-display text-3xl font-semibold tabular-nums">{stats.profiles}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">{t("home.signedCerts")}</dt>
        <dd className="font-display text-3xl font-semibold tabular-nums">{stats.certificates}</dd>
      </div>
    </dl>
  );
}
