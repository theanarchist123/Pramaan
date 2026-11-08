"use client";

import { useRef, useState } from "react";
import { FileCheck2, FileWarning, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";
import { API_URL, ApiError, getToken } from "@/lib/api";
import type { DocumentResult } from "@/lib/types";
import { cn } from "@/lib/utils";

const ACCEPT = "image/png,image/jpeg,image/webp,application/pdf,text/plain";

const FLAG_COPY: Record<string, string> = {
  identity_mismatch: "The name on this document doesn't match your profile.",
  unreadable: "We couldn't read this clearly. Try a sharper photo or the original PDF.",
  suspicious: "This document looks edited — a reviewer will take a look.",
};

export function DocumentDrop({ profileId, onDone }: { profileId: string; onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<{ name: string; r: DocumentResult }[]>([]);

  async function upload(file: File) {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API_URL}/v1/onboarding/${profileId}/documents`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: fd,
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new ApiError(res.status, body?.detail ?? "Upload failed");
      setResults((prev) => [...prev, { name: file.name, r: body }]);
      if (body.flags.length === 0) toast.success(`Read “${file.name}” — ${body.claims_verified_by_document} claim(s) verified`);
      else toast.warning(`${FLAG_COPY[body.flags[0]] ?? "Document flagged for review"} A reviewer has been notified.`);
      onDone();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          const f = e.dataTransfer.files[0];
          if (f) upload(f);
        }}
        className={cn(
          "flex w-full flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-border p-6 text-center transition-colors hover:border-primary/60 hover:bg-primary/5",
          drag && "border-primary bg-primary/5",
        )}
        disabled={busy}
      >
        {busy ? <Loader2 className="size-6 animate-spin text-primary" /> : <Upload className="size-6 text-muted-foreground" />}
        <span className="text-sm font-medium">{busy ? "Lipik is reading your document…" : "Add a certificate, award letter or degree"}</span>
        <span className="text-xs text-muted-foreground">Photo or PDF, up to 8 MB. A matching document is what unlocks automatic approval.</span>
      </button>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) upload(f);
          e.target.value = "";
        }}
      />
      {results.length > 0 && (
        <ul className="space-y-2">
          {results.map(({ name, r }) => {
            const ok = r.flags.length === 0;
            return (
              <li key={r.document_id} className="flex gap-3 rounded-xl border border-border p-3 text-sm">
                {ok ? <FileCheck2 className="size-5 shrink-0 text-verified" /> : <FileWarning className="size-5 shrink-0 text-destructive" />}
                <div className="min-w-0">
                  <p className="truncate font-medium">{name}</p>
                  <p className="text-xs text-muted-foreground">
                    {r.extracted.title || r.extracted.doc_type}
                    {r.extracted.holder_name && ` · holder: ${r.extracted.holder_name} (${Math.round(r.match_score * 100)}% match)`}
                  </p>
                  {!ok && <p className="mt-1 text-xs text-destructive">{FLAG_COPY[r.flags[0]] ?? r.flags.join(", ")}</p>}
                  {r.sent_to_review && <p className="mt-1 text-xs text-muted-foreground">Sent to a human reviewer. You&apos;ll see the result on your profile.</p>}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
