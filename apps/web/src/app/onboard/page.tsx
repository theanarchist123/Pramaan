"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatPanel, type ChatMessage } from "@/components/onboarding/chat-panel";
import { ConsentStep, type ConsentChoice } from "@/components/onboarding/consent-step";
import { DiscoveryCard } from "@/components/onboarding/discovery-card";
import { DocumentDrop } from "@/components/onboarding/document-drop";
import { ProfilePanel } from "@/components/onboarding/profile-panel";
import { Eligibility } from "@/components/onboarding/eligibility";
import { Journey } from "@/components/onboarding/journey";
import { PhotoUpload } from "@/components/onboarding/photo-upload";
import { SaveProgress } from "@/components/onboarding/save-progress";
import { NextStep } from "@/components/onboarding/next-step";
import { SaathiMascot, type SaathiState } from "@/components/onboarding/saathi-mascot";
import { celebrate } from "@/lib/celebrate";
import { useMotionPreference } from "@/lib/motion-preference";
import { VerifyPanel } from "@/components/onboarding/verify-panel";
import { useAgentStream } from "@/hooks/use-agent-stream";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DiscoveryResult, Profile, TurnOut } from "@/lib/types";

export default function OnboardPage() {
  const { user, ready, startGuest } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [thinking, setThinking] = useState(false);
  const [discovery, setDiscovery] = useState<DiscoveryResult | null>(null);
  const [applying, setApplying] = useState(false);
  const [verifyRun, setVerifyRun] = useState<string | null>(null);
  const [delighted, setDelighted] = useState(false);
  const [listening, setListening] = useState(false);
  const { reduced } = useMotionPreference();
  const focusSection = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
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
      void celebrate(reduced); // the server has confirmed it: this is a real event
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
      // A visitor sees the start screen first and chooses their consent; an account is asked for only when they continue.
      setLoading(false);
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
          focusSection("sec-verify");
        }
        else toast.info("A human reviewer will take it from here — see the reasons in the Verify tab.");      });
    }
  }, [events, verifyRun, refresh]);

  async function start(c: ConsentChoice) {
    if (!user) {
      // No account yet: carry on as a guest. The draft is kept when they create an account.
      try {
        await startGuest();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Couldn't start. Please try again.");
        return;
      }
    }
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
      // Fact capture: mark, in the person's own message, the exact words each new fact was recorded from.
      const quotes = turn.new_claims.flatMap((c) => c.evidence.filter((e) => e.kind === "chat").map((e) => e.quote));
      setMessages((m) => {
        const next = [...m];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].role === "user") {
            next[i] = { ...next[i], captured: quotes };
            break;
          }
        }
        return [...next, { role: "assistant", content: turn.reply }];
      });
      setProfile(turn.profile);
      if (turn.new_claims.length) {
        toast.success(`Added ${turn.new_claims.length} achievement(s) to your profile`);
        setDelighted(true); // the server recorded something new
        window.setTimeout(() => setDelighted(false), 1800);
      }
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
      focusSection("sec-verify");
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

  // Saathi's mood comes from real state only: the microphone, a pending reply, or something the server just recorded.
  const mood: SaathiState = listening ? "listening" : thinking ? "thinking" : delighted ? "delighted" : "idle";
  const moodLine = { idle: "Tell me about your work. Speak or type.", listening: "I'm listening…", thinking: "Thinking…", delighted: "Got it. I've added that to your profile." }[mood];

  return (
    <div className="mx-auto grid w-full gap-5 px-4 pb-4 sm:px-6 lg:h-[calc(100dvh-4.25rem)] lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)] lg:overflow-hidden">
      {/* The conversation: Saathi on a dark band, the chat below. */}
      <div className="pop relative flex h-[78dvh] min-h-0 flex-col overflow-hidden rounded-[2rem] bg-card lg:h-auto">
        <div className="flex items-center gap-4 bg-[#14152B] px-5 py-4 text-white">
          <div className="shrink-0 rounded-full bg-white/5 p-1"><SaathiMascot state={mood} size={88} /></div>
          <div className="min-w-0">
            <h1 className="text-3xl leading-none">Saathi</h1>
            <p className="mt-1.5 text-sm text-white/75" aria-live="polite">{moodLine}</p>
          </div>
        </div>
        <ChatPanel
          messages={messages}
          thinking={thinking}
          onSend={send}
          onListeningChange={setListening}
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
                ? "Your profile is being verified, so chat is paused to keep the evidence consistent."
                : "Your profile is with a reviewer. You can still add documents on the right."
          }
          header={
            discovery?.draft ? (
              <DiscoveryCard result={discovery} busy={applying} onConfirm={confirmDiscovery} onReject={() => setDiscovery(null)} />
            ) : null
          }
        />
      </div>

      {/* Your progress: what to do next, then the pieces, each with its own colour. */}
      <div className="relative h-[80dvh] min-h-0 space-y-4 overflow-y-auto pr-1 lg:h-auto">
        {user?.is_guest && <SaveProgress />}
        <div className="sticky top-0 z-10 bg-background pb-1 pt-1">
          <NextStep
            profile={profile}
            certCode={certCode}
            running={Boolean(verifyRun)}
            issuing={issuing}
            onVerify={verify}
            onIssue={issue}
            onTalk={() => document.getElementById("chat-input")?.focus()}
            onDocs={() => focusSection("sec-documents")}
            onPhoto={() => { focusSection("sec-profile"); document.getElementById("photo-input")?.click(); }}
          />
        </div>
        <Journey profile={profile} certCode={certCode} />
        <Section id="sec-profile" n={1} title="Your profile, live">
          <PhotoUpload profile={profile} onDone={() => void refresh()} />
          <ProfilePanel profile={profile} />
        </Section>
        <Eligibility profile={profile} />
        <Section id="sec-documents" n={2} title="Back it up with a document">
          <p className="-mt-2 mb-4 text-sm text-muted-foreground">
            We read it and check that the name and the issuer match. A claim shows as <em>document verified</em> only when they do.
          </p>
          <DocumentDrop profileId={profile.id} onDone={refresh} />
        </Section>
        <Section id="sec-verify" n={3} title="Check and certificate">
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
        </Section>
      </div>
    </div>
  );
}

function Section({ id, n, title, children }: { id: string; n: number; title: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="rounded-[1.8rem] border border-border bg-card p-5">
      <h2 id={`${id}-h`} className="mb-4 flex items-center gap-3 text-2xl">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-xl font-display text-lg font-extrabold" style={{ background: `var(--tile${n})`, color: `var(--tile${n}i)` }}>{n}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}
