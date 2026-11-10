"use client";

import Link from "next/link";
import { Award, BadgeCheck, Clock, Download, ExternalLink, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AgentFeed } from "@/components/agent-feed";
import { EmailVerify } from "@/components/onboarding/email-verify";
import { WikidataConfirm } from "@/components/onboarding/wikidata-confirm";
import { Certificate } from "@/components/certificate/certificate";
import { ScaledTilt } from "@/components/certificate/scaled-tilt";
import { toCertificateData, useCertificate } from "@/hooks/use-certificate";
import { API_URL } from "@/lib/api";
import type { AgentEvent, Profile } from "@/lib/types";

function CertificateCard({ code }: { code: string }) {
  const { detail } = useCertificate(code);
  const data = detail ? toCertificateData(detail) : null;
  return (
    <div className="space-y-3">
      {data ? (
        <ScaledTilt>
          <Certificate data={data} />
        </ScaledTilt>
      ) : (
        <Skeleton className="aspect-[1123/794] w-full rounded-xl" />
      )}
      <div className="flex gap-2">
        <Button className="flex-1" render={<Link href={`/verify/${code}`} />} nativeButton={false}>
          <ExternalLink /> Open verification page
        </Button>
        <Button variant="outline" render={<a href={`${API_URL}/v1/certificates/${code}/pdf`} download />} nativeButton={false}>
          <Download /> PDF
        </Button>
      </div>
    </div>
  );
}

export function VerifyPanel({
  profile,
  events,
  running,
  certificateCode,
  issuing,
  onVerify,
  onIssue,
  onProfileChange,
}: {
  profile: Profile;
  events: AgentEvent[];
  running: boolean;
  certificateCode: string | null;
  issuing: boolean;
  onVerify: () => void;
  onIssue: () => void;
  onProfileChange?: () => void;
}) {
  const canVerify = profile.claims.length > 0 && ["draft", "rejected"].includes(profile.status);
  // Prahari's latest verdict carries the human-readable reasons.
  const verdict = [...events].reverse().find((e) => e.agent === "Prahari" && e.kind === "result");
  const reasons = ((verdict?.data as { reasons?: string[] } | undefined)?.reasons ?? []) as string[];

  return (
    <div className="space-y-4">
      <EmailVerify />
      <WikidataConfirm profile={profile} onChanged={() => onProfileChange?.()} />
      {profile.status === "approved" ? (
        <div className="flex gap-3 rounded-2xl bg-verified-soft p-4">
          <BadgeCheck className="size-6 shrink-0 text-verified" />
          <div>
            <p className="font-semibold">
              {profile.decision_basis === "reviewer"
                ? "Reviewed and approved by a person"
                : profile.decision_basis === "automation"
                  ? "Passed automated checks"
                  : "Approved"}
            </p>
            <p className="text-sm text-muted-foreground">
              {profile.decision_basis === "reviewer"
                ? "A reviewer looked at your evidence and approved your record."
                : "Every claim below shows how it was checked."}{" "}
              {certificateCode ? "Here is your signed certificate." : "Your signed certificate is next."}
            </p>
          </div>
        </div>
      ) : null}
      {profile.status === "approved" ? (
        certificateCode ? (
          <CertificateCard code={certificateCode} />
        ) : (
          <Button className="h-11 w-full text-base" disabled={issuing} onClick={onIssue}>
            <Award /> {issuing ? "Signing your certificate…" : "Issue my signed certificate"}
          </Button>
        )
      ) : profile.status === "pending_review" && !running ? (
        <div className="flex gap-3 rounded-2xl bg-pending-soft p-4">
          <Clock className="size-6 shrink-0 text-pending" />
          <div>
            <p className="font-semibold">With a reviewer</p>
            <p className="text-sm text-muted-foreground">
              We couldn&apos;t confirm everything automatically, so a person will look at it. Nothing is published as verified until then.
            </p>
            {reasons.length > 0 && (
              <ul className="mt-2 space-y-1 text-sm">
                {reasons.map((r) => (
                  <li key={r} className="flex gap-2">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-pending" /> {r}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-sm text-muted-foreground">Adding a matching document usually helps most.</p>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-border p-4">
          <p className="flex items-center gap-2 font-semibold">
            <ShieldCheck className="size-5 text-indigo" /> Ready when you are
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Pariksha will check every claim against public sources; Prahari decides whether a human needs to look.
            Nothing is approved below 95% confidence.
          </p>
          <Button className="mt-3 h-10 w-full" disabled={!canVerify || running} onClick={onVerify}>
            {running ? "Agents are working…" : "Verify my profile"}
          </Button>
          {!canVerify && profile.claims.length === 0 && (
            <p className="mt-2 text-xs text-muted-foreground">Tell Saathi about at least one achievement first.</p>
          )}
        </div>
      )}

      <div>
        <h3 className="mb-2 text-sm font-semibold">What the agents are doing</h3>
        <AgentFeed events={events} emptyText="Agent activity for your profile will stream here." />
      </div>
    </div>
  );
}
