"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface Grant { id: string; client_name: string; scopes: string[]; since: string }

/** Apps the member has let in through "Allow" on the consent screen. Names and permissions only; removing one stops it at once. */
export function AuthorizedApps() {
  const [grants, setGrants] = useState<Grant[] | null>(null);
  const load = useCallback(() => api<Grant[]>("/v1/oauth/grants").then(setGrants).catch(() => setGrants([])), []);
  useEffect(() => void load(), [load]);

  async function remove(g: Grant) {
    if (!confirm(`Remove “${g.client_name}”? It will stop working immediately.`)) return;
    await api(`/v1/oauth/grants/${g.id}`, { method: "DELETE" });
    toast.success("App removed");
    load();
  }

  return (
    <section className="mt-10" aria-label="Apps you have allowed">
      <h3 className="text-lg font-semibold">Apps you have allowed</h3>
      {grants === null ? null : grants.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">None. An app only appears here after you press Allow on its request.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {grants.map((g) => (
            <li key={g.id} className="flex items-start justify-between gap-3 rounded-xl border border-border bg-card p-3">
              <div className="min-w-0">
                <p className="font-medium">{g.client_name}</p>
                <p className="text-xs text-muted-foreground">{g.scopes.join(", ")} · since {new Date(g.since).toLocaleDateString()}</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => remove(g)}>Remove</Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
