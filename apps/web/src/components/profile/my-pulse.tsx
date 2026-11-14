"use client";

import { useCallback, useEffect, useState } from "react";
import NumberFlow from "@number-flow/react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";

interface Insights { views_total: number; checks_total: number; intros_pending: number; last_7_days: { day: string; views: number; checks: number }[] }
interface Intro { id: string; profile_id: string; from_name: string; message: string; status: string }

/** For the owner: how often the page was opened and the certificate checked (counts only), and who asked to be introduced. */
export function MyPulse({ profileId }: { profileId: string }) {
  const [ins, setIns] = useState<Insights | null>(null);
  const [intros, setIntros] = useState<Intro[]>([]);

  const load = useCallback(() => {
    api<Insights>(`/v1/profiles/${profileId}/insights`).then(setIns).catch(() => {});
    api<Intro[]>("/v1/intros/incoming").then((l) => setIntros(l.filter((i) => i.profile_id === profileId))).catch(() => {});
  }, [profileId]);
  useEffect(() => { load(); }, [load]);

  async function answer(i: Intro, accept: boolean) {
    try {
      await api(`/v1/intros/${i.id}/respond`, { method: "POST", json: { accept } });
      toast.success(accept ? "Accepted. They'll be told you're open to it." : "Declined");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't answer");
    }
  }

  if (!ins) return null;
  const max = Math.max(1, ...ins.last_7_days.map((d) => d.views));
  return (
    <section className="mt-6" aria-label="How it's going">
      <h3 className="text-xl">How it&apos;s going</h3>
      <dl className="mt-3 grid grid-cols-3 gap-3">
        {[
          ["Page views", ins.views_total],
          ["Certificate checks", ins.checks_total],
          ["Introduction requests", ins.intros_pending],
        ].map(([label, n]) => (
          <div key={String(label)} className="rounded-2xl bg-[var(--stamp-tint)] p-3.5">
            <dd className="font-display text-3xl font-extrabold tabular-nums"><NumberFlow value={Number(n)} /></dd>
            <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
          </div>
        ))}
      </dl>
      <div className="mt-3 flex h-12 items-end gap-1.5" role="img" aria-label={`Page views over the last 7 days: ${ins.last_7_days.map((d) => d.views).join(", ")}`}>
        {ins.last_7_days.map((d) => (
          <span key={d.day} title={`${d.day}: ${d.views}`} className="flex-1 rounded-t-md bg-[var(--brand)]" style={{ height: `${Math.max(6, (d.views / max) * 100)}%` }} />
        ))}
      </div>
      {intros.length > 0 && (
        <ul className="mt-4 space-y-2">
          {intros.map((i) => (
            <li key={i.id} className="rounded-2xl border border-border p-3.5">
              <p className="text-sm"><b>{i.from_name || "Someone"}</b> would like to be introduced:</p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">{i.message}</p>
              {i.status === "pending" ? (
                <div className="mt-2 flex gap-2">
                  <Button size="sm" onClick={() => answer(i, true)}>Accept</Button>
                  <Button size="sm" variant="outline" onClick={() => answer(i, false)}>Decline</Button>
                </div>
              ) : (
                <p className="mt-2 text-xs font-semibold capitalize">{i.status}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
