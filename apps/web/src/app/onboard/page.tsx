"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Bot, FileText, UserRound } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatPanel, type ChatMessage } from "@/components/onboarding/chat-panel";
import { ConsentStep, type ConsentChoice } from "@/components/onboarding/consent-step";
import { DiscoveryCard } from "@/components/onboarding/discovery-card";
import { DocumentDrop } from "@/components/onboarding/document-drop";
import { ProfilePanel } from "@/components/onboarding/profile-panel";
import { StatusStepper } from "@/components/onboarding/status-stepper";
import { VerifyPanel } from "@/components/onboarding/verify-panel";
import { useAgentStream } from "@/hooks/use-agent-stream";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DiscoveryResult, Profile, TurnOut } from "@/lib/types";

export default function OnboardPage() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [thinking, setThinking] = useState(false);
  const [discovery, setDiscovery] = useState<DiscoveryResult | null>(null);
  const [applying, setApplying] = useState(false);
  const [verifyRun, setVerifyRun] = useState<string | null>(null);
  const [tab, setTab] = useState("profile");
  const [certCode, setCertCode] = useState<string | null>(null);
  const [issuing, setIssuing] = useState(false);

  const { events } = useAgentStream(profile?.id, Boolean(profile));

  // An approved profile may already have a certificate (e.g. returning later).
  useEffect(() => {
    if (profile?.status !== "approved") return;
    api<{ code: string }[]>(`/v1/profiles/${profile.id}/certificates`)
      .then((c) => setCertCode(c[0]?.code ?? null))
      .catch(() => {});
  }, [profile?.id, profile?.status]);

  async function issue() {
    if (!profile) return;
    setIssuing(true);
    try {
      const cert = await api<{ code: string }>(`/v1/profiles/${profile.id}/certificate`, { method: "POST" });
      setCertCode(cert.code);
      toast.success("Certificate signed and added to the public log");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't issue the certificate");
    } finally {
      setIssuing(false);
    }
  }

  const refresh = useCallback(async (): Promise<Profile | undefined> => {
    const mine = await api<Profile[]>("/v1/profiles/mine");
    const current = mine.find((p) => p.id === profile?.id) ?? mine[0];
    if (current) setProfile(current);
    return current;
  }, [profile?.id]);

  // Auth gate + resume the most recent profile.
  useEffect(() => {
    if (!ready) return;
    if (!user) {
      router.replace("/auth?next=/onboard");
      return;
    }
    (async () => {
      try {
        const mine = await api<Profile[]>("/v1/profiles/mine");
        const resume = mine[0];
        if (resume) {
          setProfile(resume);
          const history = await api<ChatMessage[]>(`/v1/onboarding/${resume.id}/messages`);
          setMessages(history.map(({ role, content }) => ({ role, content })));
        }
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Couldn't load your profile");
      } finally {
        setLoading(false);
      }
    })();
  }, [ready, user, router]);

  // When the verification run finishes, pull the final state.
  useEffect(() => {
    if (!verifyRun) return;
    const done = events.find((e) => e.run_id === verifyRun && e.kind === "run_finished");
    if (done) {
      setVerifyRun(null);
      // Tell the person the actual outcome, not just that the workflow ended.
      refresh().then((p) => {
        if (p?.status === "approved") {
          toast.success("Verified! Your profile passed every check.");
          setTab("agents");
        }
        else toast.info("A human reviewer will take it from here — see the reasons in the Verify tab.");      });
    }
  }, [events, verifyRun, refresh]);

  async function start(c: ConsentChoice) {
    setStarting(true);
    try {
      const r = await api<{ profile: Profile; greeting: string }>("/v1/onboarding/start", {
        method: "POST",
        json: { full_name: c.name || null, consent_public_listing: c.publicListing, consent_web_research: c.webResearch },
      });
      setProfile(r.profile);
      setMessages([{ role: "assistant", content: r.greeting }]);
      if (c.name && c.webResearch) {
        api<DiscoveryResult>("/v1/onboarding/discover", { method: "POST", json: { name: c.name } })
          .then((d) => d.found && d.draft && setDiscovery(d))
          .catch(() => {});
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't start");
    } finally {
      setStarting(false);
    }
  }

  async function send(text: string) {
    if (!profile) return;
    setMessages((m) => [...m, { role: "user", content: text }]);
    setThinking(true);
    try {
      const turn = await api<TurnOut>(`/v1/onboarding/${profile.id}/message`, { method: "POST", json: { text } });
      setMessages((m) => [...m, { role: "assistant", content: turn.reply }]);
      setProfile(turn.profile);
      if (turn.new_claims.length) toast.success(`Added ${turn.new_claims.length} achievement(s) to your profile`);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: err instanceof ApiError ? err.message : "Sorry — something went wrong. Please try again." },
      ]);
    } finally {
      setThinking(false);
    }
  }

  async function confirmDiscovery() {
    if (!profile || !discovery?.draft) return;
    setApplying(true);
    try {
      const p = await api<Profile>(`/v1/onboarding/${profile.id}/apply-discovery`, {
        method: "POST",
        json: { draft: discovery.draft, source_url: discovery.source_url },
      });
      setProfile(p);
      setDiscovery(null);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Wonderful — I've added what I found. Is anything missing or out of date? Tell me in your own words." },
      ]);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't apply");
    } finally {
      setApplying(false);
    }
  }

  async function verify() {
    if (!profile) return;
    try {
      const r = await api<{ run_id: string }>(`/v1/onboarding/${profile.id}/verify`, { method: "POST" });
      setVerifyRun(r.run_id);
      setTab("agents");
      setProfile({ ...profile, status: "pending_review" });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't start verification");
    }
  }

  if (!ready || loading) {
    return (
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 lg:grid-cols-2">
        <Skeleton className="h-[70vh] rounded-2xl" />
        <Skeleton className="h-[70vh] rounded-2xl" />
      </div>
    );
  }

  if (!profile) return <ConsentStep busy={starting} onStart={start} />;

  const editable = ["draft", "rejected"].includes(profile.status);
  // The Verify tab tells the verification story; chat-turn bookkeeping would only bury it.
  const profileEvents = events.filter(
    (e) => e.profile_id === profile.id && e.workflow !== "onboarding_turn",
  );

  return (
    <div className="mx-auto grid max-w-7xl gap-4 px-4 py-4 lg:h-[calc(100dvh-3.5rem)] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:py-6">
      <div className="flex h-[70dvh] min-h-0 flex-col overflow-hidden rounded-2xl border border-border bg-card lg:h-auto">
        <ChatPanel
          messages={messages}
          thinking={thinking}
          onSend={send}
          disabled={!editable}
          disabledReason={
            profile.status === "suspended"
              ? "The registry has suspended this profile, so it can't be edited. Contact the registry for the reason."
              : profile.status === "approved"
              ? profile.decision_basis === "reviewer"
                ? "Your profile was reviewed and approved by a person."
                : profile.decision_basis === "automation"
                  ? "Your profile passed automated checks."
                  : "Your profile is approved."
              : verifyRun
                ? "Your profile is being verified — chat is paused so the evidence stays consistent."
                : "Your profile is with a reviewer. You can still add documents in the Documents tab."
          }
          header={
            discovery?.draft ? (
              <DiscoveryCard result={discovery} busy={applying} onConfirm={confirmDiscovery} onReject={() => setDiscovery(null)} />
            ) : null
          }
        />
      </div>

      <div className="h-[80dvh] min-h-0 overflow-hidden rounded-2xl border border-border bg-card lg:h-auto">
        <Tabs value={tab} onValueChange={(v) => setTab(String(v))} className="flex h-full flex-col">
          <div className="border-b border-border px-4 pt-3 pb-2">
            <div className="mb-3"><StatusStepper profile={profile} /></div>
            <TabsList>
              <TabsTrigger value="profile"><UserRound /> Profile</TabsTrigger>
              <TabsTrigger value="documents"><FileText /> Documents</TabsTrigger>
              <TabsTrigger value="agents">
                <Bot /> Verify
                {verifyRun && <span className="size-1.5 animate-pulse rounded-full bg-primary" />}
              </TabsTrigger>
            </TabsList>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            <TabsContent value="profile">
              <ProfilePanel profile={profile} />
            </TabsContent>
            <TabsContent value="documents">
              <h2 className="text-xl font-semibold">Back it up with a document</h2>
              <p className="mb-4 mt-1 text-sm text-muted-foreground">
                Lipik reads it and checks that the name and the issuer match. A claim shows as{" "}
                <em>document verified</em> only when they do.
              </p>
              <DocumentDrop profileId={profile.id} onDone={refresh} />
            </TabsContent>
            <TabsContent value="agents">
              <VerifyPanel
                profile={profile}
                events={profileEvents}
                running={Boolean(verifyRun)}
                certificateCode={certCode}
                issuing={issuing}
                onVerify={verify}
                onIssue={issue}
                onProfileChange={() => void refresh()}
              />
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  );
}
