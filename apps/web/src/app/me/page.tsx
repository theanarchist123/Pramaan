"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Profile } from "@/lib/types";

export default function MyProfiles() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const [profiles, setProfiles] = useState<Profile[] | null>(null);

  useEffect(() => {
    if (!ready) return;
    if (!user) router.replace("/auth?next=/me");
    else api<Profile[]>("/v1/profiles/mine").then(setProfiles).catch(() => setProfiles([]));
  }, [ready, user, router]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-4xl font-semibold">My profiles</h1>
      <ul className="mt-6 space-y-3">
        {profiles?.map((p) => (
          <li key={p.id} className="flex items-center justify-between rounded-2xl border border-border bg-card p-4">
            <div>
              <p className="font-display text-xl font-semibold">{p.full_name}</p>
              <p className="text-sm text-muted-foreground">
                {p.status.replace("_", " ")} · {p.claims.filter((c) => c.status !== "self").length}/{p.claims.length} claims verified
              </p>
            </div>
            <Button variant="outline" render={<Link href="/onboard" />} nativeButton={false}>Open</Button>
          </li>
        ))}
        {profiles?.length === 0 && (
          <li className="rounded-2xl border border-dashed border-border p-8 text-center text-muted-foreground">
            No profile yet. <Link href="/onboard" className="text-primary underline">Start one with Saathi</Link>.
          </li>
        )}
      </ul>
    </div>
  );
}
