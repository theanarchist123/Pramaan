"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { Profile } from "@/lib/types";

interface Candidate {
  qid: string;
  label: string;
  description: string;
  born: string;
  url: string;
}

/**
 * "Is this you?" on Wikidata. Many people share a name, so the pipeline never guesses: you pick your own entry (or none),
 * and only that entry is ever used as evidence about you.
 */
export function WikidataConfirm({ profile, onChanged }: { profile: Profile; onChanged: () => void }) {
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [confirmed, setConfirmed] = useState<string | null>(profile.wikidata_qid || null);
  const [busy, setBusy] = useState(false);
  const editable = ["draft", "rejected"].includes(profile.status);
  const named = profile.full_name && profile.full_name !== "New Profile";

  useEffect(() => {
    if (!editable || !named) return;
    api<{ confirmed_qid: string | null; candidates: Candidate[] }>(`/v1/onboarding/${profile.id}/wikidata-candidates`)
      .then((r) => {
        setCandidates(r.candidates);
        setConfirmed(r.confirmed_qid);
      })
      .catch(() => setCandidates([]));
  }, [profile.id, profile.full_name, editable, named]);

  if (!editable || !named || !candidates || candidates.length === 0) return null;

  async function choose(qid: string | null) {
    setBusy(true);
    try {
      await api(`/v1/onboarding/${profile.id}/wikidata-confirm`, { method: "POST", json: { qid } });
      setConfirmed(qid);
      onChanged();
      toast.success(qid ? "Thanks, we'll check your claims against that entry" : "Okay, we won't use Wikidata for you");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't save your choice");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2 rounded-2xl border border-border p-4">
      <p className="font-semibold">Are you one of these people on Wikidata?</p>
      <p className="text-sm text-muted-foreground">
        Several people can share a name. Choose your own entry so we only check your claims against facts about you.
      </p>
      <ul className="space-y-2">
        {candidates.map((c) => (
          <li key={c.qid} className="flex items-center justify-between gap-3 rounded-xl border border-border p-3">
            <div className="min-w-0 text-sm">
              <a href={c.url} target="_blank" rel="noreferrer" className="font-medium underline-offset-2 hover:underline">{c.label}</a>
              <p className="text-muted-foreground">{[c.description, c.born && `born ${c.born}`].filter(Boolean).join(" · ") || "No description"}</p>
            </div>
            <Button size="sm" variant={confirmed === c.qid ? "default" : "outline"} disabled={busy} onClick={() => choose(confirmed === c.qid ? null : c.qid)}>
              {confirmed === c.qid ? "That's me ✓" : "That's me"}
            </Button>
          </li>
        ))}
      </ul>
      {confirmed && <button type="button" className="text-xs text-muted-foreground underline" onClick={() => choose(null)}>None of these is me</button>}
    </div>
  );
}
