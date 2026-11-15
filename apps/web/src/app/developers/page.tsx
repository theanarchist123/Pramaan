"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ExternalLink, FlaskConical, KeyRound, Rocket, ShieldCheck, Webhook } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiKeys } from "@/components/developers/api-keys";
import { AuthorizedApps } from "@/components/developers/authorized-apps";
import { BadgeGenerator } from "@/components/developers/badge";
import { Playground } from "@/components/developers/playground";
import { Quickstart } from "@/components/developers/quickstart";
import { Webhooks } from "@/components/developers/webhooks";
import { API_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const SECTIONS = [
  { id: "start", label: "Quickstart", icon: Rocket },
  { id: "play", label: "Playground", icon: FlaskConical },
  { id: "keys", label: "API keys", icon: KeyRound, auth: true },
  { id: "hooks", label: "Webhooks", icon: Webhook, auth: true },
  { id: "badge", label: "Badges", icon: ShieldCheck },
] as const;

function SignInPrompt({ what }: { what: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border p-10 text-center">
      <p className="font-medium">Sign in to manage {what}.</p>
      <Button className="mt-3" render={<Link href="/auth?next=/developers" />} nativeButton={false}>Sign in</Button>
    </div>
  );
}

export default function Developers() {
  const { user, ready } = useAuth();
  const [section, setSection] = useState<(typeof SECTIONS)[number]["id"]>("start");

  // Sections are deep-linkable: /developers#play opens the playground, and choosing a tab updates the address.
  useEffect(() => {
    const fromHash = () => {
      const id = window.location.hash.slice(1);
      const hit = SECTIONS.find((x) => x.id === id);
      if (hit) setSection(hit.id);
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
  }, []);
  const choose = (id: (typeof SECTIONS)[number]["id"]) => {
    setSection(id);
    history.replaceState(null, "", `#${id}`);
  };
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = SECTIONS[(i + step + SECTIONS.length) % SECTIONS.length];
    choose(next.id);
    document.getElementById(`tab-${next.id}`)?.focus();
  };

  return (
    <div className="md:-mt-16">
      <section className="bg-[var(--tile5)] text-[var(--tile5i)]">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 pb-14 pt-8 md:pt-28 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <h1 className="text-balance text-5xl leading-[1.02] md:text-7xl">Build on Pramaan.</h1>
            <p className="mt-4 max-w-xl text-lg">
              Check a certificate from your own app with one request. No key needed to verify. Keys, webhooks and an MCP server are here when you need more.
            </p>
          </div>
          <pre aria-label="Example request" className="pop overflow-x-auto rounded-3xl bg-[#14152B] p-5 text-sm leading-relaxed text-white"><code>{`$ curl ${API_URL}/v1/verify/PRM-XXXXXXXXXX

{
  "valid": true,
  "signature_ok": true,
  "chain_ok": true,
  "revoked": false
}`}</code></pre>
        </div>
      </section>
      <div className="mx-auto max-w-6xl px-4 py-10">
      <p className="sr-only">Everything this app does is available through a versioned public API and signed webhooks.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="outline" size="sm" render={<a href={`${API_URL}/docs`} target="_blank" rel="noreferrer" />} nativeButton={false}>
          Interactive API reference <ExternalLink />
        </Button>
        <Button variant="outline" size="sm" render={<a href={`${API_URL}/openapi.json`} target="_blank" rel="noreferrer" />} nativeButton={false}>
          openapi.json <ExternalLink />
        </Button>
        <Button variant="outline" size="sm" render={<Link href="/transparency" />} nativeButton={false}>Transparency log</Button>
      </div>

      <div role="tablist" aria-label="Developer sections" className="mt-8 flex flex-wrap gap-1 border-b border-border">
        {SECTIONS.map(({ id, label, icon: Icon }, i) => (
          <button
            key={id}
            id={`tab-${id}`}
            role="tab"
            aria-selected={section === id}
            aria-controls="dev-panel"
            tabIndex={section === id ? 0 : -1}
            onKeyDown={(e) => onKey(e, i)}
            onClick={() => choose(id)}
            className={cn(
              "-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
              section === id ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon aria-hidden className="size-4" /> {label}
          </button>
        ))}
      </div>

      <div className="mt-8" role="tabpanel" id="dev-panel" aria-labelledby={`tab-${section}`}>
        {section === "start" && <Quickstart />}
        {section === "play" && <Playground />}
        {section === "keys" && (ready && user ? <><ApiKeys /><AuthorizedApps /></> : <SignInPrompt what="API keys" />)}
        {section === "hooks" && (ready && user ? <Webhooks /> : <SignInPrompt what="webhooks" />)}
        {section === "badge" && <BadgeGenerator />}
      </div>
      </div>
    </div>
  );
}
