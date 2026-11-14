"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Eye } from "lucide-react";
import { Journey } from "@/components/onboarding/journey";
import { MyPulse } from "@/components/profile/my-pulse";
import { Avatar } from "@/components/profile/avatar";
import { ShareRow } from "@/components/share-row";
import { StatusTag, type StatusKind } from "@/components/ui/status-tag";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Profile } from "@/lib/types";

const STATUS_TEXT: Record<string, string> = {
  draft: "Draft: keep talking to Saathi to finish it",
  pending_review: "With a reviewer",
  approved: "Approved and public",
  rejected: "Needs changes",
  suspended: "Hidden by the registry",
};

/** The next best action, derived only from server state. */
function nextAction(p: Profile): { text: string; cta: string } {
  if (p.status === "approved") return { text: "Your profile is live. Share it so people can find and check it.", cta: "Open my profile" };
  if (p.status === "pending_review") return { text: "A reviewer is looking at your profile. You can still add documents.", cta: "Add a document" };
  if (p.status === "suspended") return { text: "The registry has hidden this profile. Contact the registry for the reason.", cta: "See details" };
  if (p.claims.length === 0) return { text: "Tell Saathi about one thing you're proud of. It takes a minute.", cta: "Start talking" };
  return { text: "Add a document to one achievement, then ask for a check.", cta: "Continue" };
}

export default function MyPage() {
  const { user, ready } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [codes, setCodes] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      router.replace("/auth?mode=login&next=/me");
      return;
    }
    if (user.is_guest) {
      router.replace("/onboard"); // a guest has a draft but no account yet: back to the conversation, where they can save it
      return;
    }
    api<Profile[]>("/v1/profiles/mine")
      .then(async (mine) => {
        setProfiles(mine);
        const found: Record<string, string> = {};
        await Promise.all(
          mine.filter((p) => p.status === "approved").map((p) =>
            api<{ code: string }[]>(`/v1/profiles/${p.id}/certificates`).then((c) => { if (c[0]) found[p.id] = c[0].code; }).catch(() => {}),
          ),
        );
        setCodes(found);
      })
      .catch(() => setProfiles([]));
  }, [ready, user, router]);

  const first = (user?.name || user?.email || "").split(/[\s@]/)[0];

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="text-4xl md:text-5xl">{first ? `Hi ${first}.` : t("nav.myPage")}</h1>
      <p className="mt-2 text-muted-foreground">Here is where your profile stands and what to do next.</p>

      <div className="mt-8 space-y-8">
        {profiles === null && <div className="h-48 animate-pulse rounded-3xl bg-muted" />}
        {profiles?.map((p) => {
          const next = nextAction(p);
          const code = codes[p.id];
          return (
            <article key={p.id} className="rounded-[1.8rem] border border-border bg-card p-5 md:p-6" aria-labelledby={`p-${p.id}`}>
              <div className="flex flex-wrap items-center gap-4">
                <Avatar name={p.full_name} photo={p.photo_url} verified={p.status === "approved"} className="size-16" />
                <div className="min-w-0 flex-1">
                  <h2 id={`p-${p.id}`} className="truncate text-2xl">{p.full_name}</h2>
                  <p className="text-sm text-muted-foreground">{STATUS_TEXT[p.status] ?? p.status.replace("_", " ")}</p>
                </div>
                {p.status === "approved" && (
                  <Link href={`/p/${p.slug}`} className="inline-flex items-center gap-1.5 text-sm font-semibold underline-offset-4 hover:underline">
                    <Eye className="size-4" /> View public page
                  </Link>
                )}
              </div>

              <div className="mt-5"><Journey profile={p} certCode={code ?? null} /></div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-[var(--stamp-tint)] p-4">
                <p className="max-w-xl font-medium text-[var(--ink)]">{next.text}</p>
                <Link href="/onboard" className="inline-flex h-11 items-center gap-2 rounded-full bg-primary px-5 font-semibold text-primary-foreground">
                  {next.cta} <ArrowRight className="size-4" />
                </Link>
              </div>

              {p.claims.length > 0 && (
                <section className="mt-6" aria-label="Your achievements">
                  <h3 className="text-xl">Your achievements</h3>
                  <ul className="mt-3 grid gap-3 sm:grid-cols-2">
                    {p.claims.map((c) => (
                      <li key={c.id} className="rounded-2xl border border-border p-3.5">
                        <p className="font-semibold leading-snug">{c.value}</p>
                        <StatusTag kind={c.status as StatusKind} className="mt-2" />
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {p.status === "approved" && <MyPulse profileId={p.id} />}

              {p.status === "approved" && (
                <section className="mt-6" aria-label="Share">
                  <h3 className="text-xl">Share it</h3>
                  <ShareRow className="mt-3" url={typeof window !== "undefined" ? `${window.location.origin}/p/${p.slug}` : undefined} text={`${p.full_name}: ${p.headline || p.sector}.`} />
                  {code && (
                    <Link href={`/verify/${code}`} className="mt-3 inline-block text-sm font-semibold underline underline-offset-4">
                      See my certificate ({code})
                    </Link>
                  )}
                </section>
              )}
            </article>
          );
        })}
        {profiles?.length === 0 && (
          <div className="rounded-3xl border-2 border-dashed border-border p-10 text-center">
            <p className="font-display text-2xl font-bold">No profile yet</p>
            <p className="mt-1 text-muted-foreground">It takes about three minutes, by voice or text.</p>
            <Link href="/onboard" className="mt-5 inline-flex h-12 items-center gap-2 rounded-full bg-primary px-6 font-semibold text-primary-foreground">
              Get listed, free <ArrowRight className="size-5" />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
