"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const WORDS: Record<string, string> = {
  "verify:read": "Check whether certificates are genuine",
  "search:read": "Search the registry for you",
  "profiles:read": "Read your own profiles",
  "profiles:write": "Create and change your profiles",
};

interface Info { client_name: string; scopes: string[]; redirect_host: string }

function Consent() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const query = params.toString();

  useEffect(() => {
    if (!ready) return;
    if (!user) { router.replace(`/auth?mode=login&next=${encodeURIComponent(`/oauth/authorize?${query}`)}`); return; }
    api<Info>(`/v1/oauth/authorize?${query}`)
      .then(setInfo)
      .catch((e) => setError(e instanceof ApiError ? e.message : "This request is not valid."));
  }, [ready, user, router, query]);

  async function decide(approve: boolean) {
    setBusy(true);
    try {
      const body = Object.fromEntries(params.entries());
      const r = await api<{ redirect_to: string }>("/v1/oauth/authorize", { method: "POST", json: { ...body, approve } });
      window.location.assign(r.redirect_to); // the server only ever returns an address the app registered
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <h1 className="text-3xl font-semibold">Let an app in?</h1>
      {error ? (
        <p className="mt-6 rounded-xl border border-border bg-card p-4 text-sm" role="alert">{error} Nothing was shared. You can close this page.</p>
      ) : !info ? (
        <p className="mt-6 text-sm text-muted-foreground">Checking the request…</p>
      ) : (
        <div className="mt-6 space-y-5 rounded-2xl border border-border bg-card p-5">
          <p><strong>{info.client_name}</strong> wants to act for you on Pramaan. If you agree, it will be sent to <strong>{info.redirect_host}</strong>, and it will be able to:</p>
          <ul className="list-disc space-y-1 pl-5 text-sm">{info.scopes.map((s) => <li key={s}>{WORDS[s] ?? s}</li>)}</ul>
          <p className="text-xs text-muted-foreground">It will never be able to sign you in elsewhere, change your security settings or act as staff. You can remove it any time from the Developers page.</p>
          <div className="flex gap-2">
            <Button onClick={() => decide(true)} disabled={busy}>Allow</Button>
            <Button variant="outline" onClick={() => decide(false)} disabled={busy}>Don&apos;t allow</Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AuthorizePage() {
  return <Suspense fallback={null}><Consent /></Suspense>;
}
