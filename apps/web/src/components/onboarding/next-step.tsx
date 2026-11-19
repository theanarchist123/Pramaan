"use client";

import { ArrowRight, BadgeCheck, Camera, FileText, MessagesSquare, PartyPopper, Hourglass } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import type { Profile } from "@/lib/types";

/**
 * "What to do now", derived only from server state (claims, evidence, status, certificate): never from a timer.
 * One sentence and one button, so the person is never left wondering what comes next.
 */
export function NextStep({
  profile, certCode, running, issuing, onVerify, onIssue, onTalk, onDocs, onPhoto,
}: {
  profile: Profile; certCode: string | null; running: boolean; issuing: boolean;
  onVerify: () => void; onIssue: () => void; onTalk: () => void; onDocs: () => void; onPhoto?: () => void;
}) {
  const talked = profile.claims.length > 0;
  const documented = profile.claims.some((c) => c.evidence.some((e) => e.kind === "document"));

  let Icon = MessagesSquare;
  let title = "Tell Saathi one thing you're proud of";
  let body = "An award, a role, a project. Just say it the way you would to a friend.";
  let cta: React.ReactNode = <Button size="lg" onClick={onTalk}>Start talking <ArrowRight /></Button>;

  if (profile.status === "suspended") {
    Icon = Hourglass; title = "This profile is hidden"; body = "The registry has suspended it. Contact the registry for the reason."; cta = null;
  } else if (certCode) {
    Icon = PartyPopper; title = "Your certificate is ready"; body = "Share it, print it, or put the QR code in your email signature.";
    cta = <Button size="lg" render={<Link href={`/verify/${certCode}`} />} nativeButton={false}>See my certificate <ArrowRight /></Button>;
  } else if (profile.status === "approved") {
    Icon = BadgeCheck; title = "You're approved. Get your certificate"; body = "It's signed and added to the public log, so anyone can check it.";
    cta = <Button size="lg" disabled={issuing} onClick={onIssue}>{issuing ? "Signing…" : "Get my certificate"} <ArrowRight /></Button>;
  } else if (profile.status === "pending_review" || running) {
    Icon = Hourglass; title = running ? "Checking your facts" : "With a reviewer"; body = running ? "Matching what you said to public records and your documents." : "A person is looking at it. You can still add documents.";
    cta = null;
  } else if (!talked) {
    // defaults above
  } else if (!documented) {
    Icon = FileText; title = "Back one achievement with a document"; body = "Upload the award letter or degree. A claim becomes document verified only when the name and issuer match.";
    cta = <Button size="lg" onClick={onDocs}>Add a document <ArrowRight /></Button>;
  } else if (!profile.photo_url && onPhoto) {
    // A registry of people needs faces. Asked once, never required: the check is one tap away.
    Icon = Camera; title = "Add your photo"; body = "Profiles with a photo are trusted and found more. Use a clear photo of your face; a reviewer sees it before anyone else does.";
    cta = (
      <span className="flex flex-wrap gap-2">
        <Button size="lg" onClick={onPhoto}>Add a photo <ArrowRight /></Button>
        <Button size="lg" variant="outline" onClick={onVerify}>Skip, check my profile</Button>
      </span>
    );
  } else {
    Icon = BadgeCheck; title = "Ask for a check"; body = "We'll match everything to public records. Anything unclear goes to a person.";
    cta = <Button size="lg" onClick={onVerify}>Check my profile <ArrowRight /></Button>;
  }

  return (
    <section aria-label="Your next step" className="pop flex flex-wrap items-center gap-4 rounded-[1.6rem] bg-[var(--stamp-tint)] p-4 text-[var(--ink)]">
      <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-[var(--brand)] text-[var(--on-brand)]"><Icon aria-hidden className="size-6" /></span>
      <div className="min-w-0 flex-1 basis-56">
        <h2 className="text-xl leading-tight md:text-2xl">{title}</h2>
        <p className="mt-0.5 text-sm opacity-80">{body}</p>
      </div>
      {cta}
    </section>
  );
}
