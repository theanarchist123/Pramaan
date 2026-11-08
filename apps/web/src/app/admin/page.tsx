"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { Check, ClipboardCheck, RefreshCw, ShieldAlert, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { AdminNav } from "@/components/admin/admin-nav";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfidenceMeter, VerificationBadge } from "@/components/verification-badge";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Profile } from "@/lib/types";

interface ReviewItem {
  id: string;
  profile_id: string;
  reason: string;
  confidence: number;
  created_at: string;
  details: {
    kind?: "document" | "requested";
    flags?: string[]; coverage?: number; identity_confirmed?: boolean; verified?: number; total?: number;
    filename?: string; title?: string; issuer?: string; notes?: string;
  };
  profile: Profile | null;
}

export default function AdminPage() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [stats, setStats] = useState<{ profiles: number; certificates: number } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [q, s] = await Promise.all([
      api<ReviewItem[]>("/v1/admin/review"),
      api<{ profiles: number; certificates: number }>("/v1/stats", { auth: false }),
    ]);
    setItems(q);
    setStats(s);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!user) router.replace("/auth?next=/admin");
    else if (user.role === "admin") load().catch((e) => toast.error(e instanceof ApiError ? e.message : "Couldn't load"));
  }, [ready, user, router, load]);

  async function decide(item: ReviewItem, status: "approved" | "rejected") {
    setBusy(item.id);
    try {
      await api(`/v1/admin/profiles/${item.profile_id}/status`, { method: "POST", json: { status } });
      setItems((prev) => prev?.filter((i) => i.id !== item.id) ?? null);
      toast.success(status === "approved" ? `${item.profile?.full_name} approved and added to the directory` : "Sent back to the applicant");
      api<{ profiles: number; certificates: number }>("/v1/stats", { auth: false }).then(setStats).catch(() => {});
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  async function resolve(item: ReviewItem) {
    setBusy(item.id);
    try {
      await api(`/v1/admin/review/${item.id}/resolve`, { method: "POST", json: { note: "" } });
      setItems((prev) => prev?.filter((i) => i.id !== item.id) ?? null);
      toast.success("Review closed — the profile stays published");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  // Manual verification: the reviewer has checked the document themselves and vouches for this claim.
  async function verifyClaim(item: ReviewItem, claimId: string) {
    setBusy(claimId);
    try {
      await api(`/v1/admin/claims/${claimId}/verify`, { method: "POST", json: { status: "document", confidence: 0.97 } });
      setItems((prev) =>
        prev?.map((i) =>
          i.id !== item.id || !i.profile
            ? i
            : { ...i, profile: { ...i.profile, claims: i.profile.claims.map((c) => (c.id === claimId ? { ...c, status: "document", confidence: 0.97 } : c)) } },
        ) ?? null,
      );
      toast.success("Claim marked as document-verified");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  async function reindex() {
    setBusy("reindex");
    try {
      const r = await api<{ profiles_indexed: number; edges: number }>("/v1/admin/reindex", { method: "POST" });
      toast.success(`Reindexed ${r.profiles_indexed} profiles and ${r.edges} relationships`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Reindex failed");
    } finally {
      setBusy(null);
    }
  }

  if (!ready) return <div className="mx-auto max-w-4xl px-4 py-12"><Skeleton className="h-64 rounded-2xl" /></div>;
  if (user && user.role !== "admin") {
    return (
      <div className="mx-auto max-w-lg px-4 py-20 text-center">
        <ShieldAlert className="mx-auto size-12 text-muted-foreground" />
        <h1 className="mt-4 text-3xl font-semibold">Administrators only</h1>
        <p className="mt-2 text-muted-foreground">This area is for registry reviewers.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <AdminNav />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-4xl font-semibold">Review queue</h1>
          <p className="mt-1 max-w-xl text-muted-foreground">
            Profiles the agents weren&apos;t ≥95% sure about land here, with the reasons. Your decision publishes or returns them.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" render={<Link href="/mission-control" />} nativeButton={false}>Mission Control</Button>
          <Button variant="outline" onClick={reindex} disabled={busy === "reindex"}><RefreshCw /> Reindex</Button>
        </div>
      </div>

      <dl className="mt-6 grid grid-cols-3 gap-3">
        {[
          ["Waiting for you", items?.length ?? "–"],
          ["Verified profiles", stats?.profiles ?? "–"],
          ["Certificates issued", stats?.certificates ?? "–"],
        ].map(([label, value]) => (
          <div key={label as string} className="rounded-2xl border border-border bg-card p-4">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="font-display text-3xl font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-8 space-y-4">
        {items === null ? (
          <Skeleton className="h-56 rounded-2xl" />
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border p-14 text-center">
            <ClipboardCheck className="mx-auto size-10 text-verified" />
            <p className="mt-3 text-lg font-medium">Nothing waiting. The agents are keeping up.</p>
          </div>
        ) : (
          <AnimatePresence>
            {items.map((item) => {
              const p = item.profile;
              return (
                <motion.article
                  key={item.id}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -40 }}
                  className="rounded-2xl border border-border bg-card p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-2xl font-semibold">{p?.full_name ?? "(erased)"}</h2>
                      <p className="text-sm text-muted-foreground">
                        {[p?.headline, p?.sector, p?.state].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[11px] text-muted-foreground">Agents&apos; confidence</p>
                      <ConfidenceMeter value={item.confidence} />
                    </div>
                  </div>

                  <div className="mt-4 rounded-xl bg-pending-soft p-3 text-sm">
                    <p className="font-medium">Why a human is needed</p>
                    <p className="mt-0.5">{item.reason}</p>
                    {item.details.identity_confirmed === false && (
                      <p className="mt-1 text-xs text-muted-foreground">No document confirms this person&apos;s identity.</p>
                    )}
                    {item.details.flags && item.details.flags.length > 0 && (
                      <p className="mt-1 text-xs font-medium text-destructive">Flags: {item.details.flags.join(", ")}</p>
                    )}
                    {item.details.kind === "document" && (
                      <p className="mt-2 text-xs text-muted-foreground">
                        Document <span className="font-medium text-foreground">{item.details.filename}</span>
                        {item.details.title && <> — “{item.details.title}”</>}
                        {item.details.issuer && <> from {item.details.issuer}</>}
                        {item.details.notes && <>. Reader&apos;s notes: {item.details.notes}</>}
                      </p>
                    )}
                  </div>

                  {p && (
                    <ul className="mt-4 space-y-2">
                      {p.claims.map((c) => (
                        <li key={c.id} className="flex items-start justify-between gap-3 rounded-xl border border-border p-3 text-sm">
                          <div className="min-w-0">
                            <p>{c.value}</p>
                            {c.evidence.filter((e) => e.kind !== "chat").map((e) => (
                              <p key={e.id} className="mt-1 text-xs italic text-muted-foreground">“{e.quote.slice(0, 160)}”</p>
                            ))}
                          </div>
                          <div className="flex shrink-0 flex-col items-end gap-2">
                            <VerificationBadge status={c.status} />
                            {c.status === "self" && (
                              <Button size="sm" variant="outline" disabled={busy === c.id} onClick={() => verifyClaim(item, c.id)}>
                                <Check /> I checked it — verify
                              </Button>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}

                  <div className="mt-4 flex flex-wrap gap-2">
                    {item.details.kind ? (
                      <>
                        <Button disabled={busy === item.id} onClick={() => resolve(item)}><Check /> Done — keep published</Button>
                        <Button variant="outline" disabled={busy === item.id} onClick={() => decide(item, "rejected")}><X /> Unpublish &amp; send back</Button>
                      </>
                    ) : (
                      <>
                        <Button disabled={busy === item.id} onClick={() => decide(item, "approved")}><Check /> Approve &amp; publish</Button>
                        <Button variant="outline" disabled={busy === item.id} onClick={() => decide(item, "rejected")}><X /> Send back</Button>
                      </>
                    )}
                  </div>
                </motion.article>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
