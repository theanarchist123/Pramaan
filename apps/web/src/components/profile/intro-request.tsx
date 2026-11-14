"use client";

import { useState } from "react";
import Link from "next/link";
import { HandHeart } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Ask to be introduced. The note is cleaned on the server (links and contact details removed); nobody's address is exposed by asking. */
export function IntroRequest({ slug, name }: { slug: string; name: string }) {
  const { user, ready } = useAuth();
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function send() {
    setBusy(true);
    try {
      await api(`/v1/profiles/${slug}/intro`, { method: "POST", json: { message: msg } });
      setSent(true);
      toast.success("Request sent. They'll see your note, not your email.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't send the request");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="intro-h" className="rounded-3xl border border-border bg-card p-5">
      <h2 id="intro-h" className="flex items-center gap-2 text-xl"><HandHeart aria-hidden className="size-5" /> Want to meet {name.split(" ")[0]}?</h2>
      {sent ? (
        <p className="mt-2 text-sm text-muted-foreground">Sent. If they accept, you&apos;ll hear from them.</p>
      ) : !open ? (
        <>
          <p className="mt-1 text-sm text-muted-foreground">Ask for an introduction. They decide whether to reply.</p>
          {ready && !user ? (
            <Button className="mt-3" render={<Link href={`/auth?mode=login&next=/p/${slug}`} />} nativeButton={false}>Sign in to ask</Button>
          ) : (
            <Button className="mt-3" onClick={() => setOpen(true)}>Request an introduction</Button>
          )}
        </>
      ) : (
        <div className="mt-3 space-y-2">
          <label htmlFor="intro-msg" className="text-sm font-medium">Why would you like to be introduced?</label>
          <Textarea id="intro-msg" rows={4} maxLength={1000} value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="e.g. I'm organising a conference on clean energy and would love you to speak." />
          <p className="text-xs text-muted-foreground">Links and contact details are removed from your note. Your email isn&apos;t shared.</p>
          <div className="flex gap-2">
            <Button disabled={busy || msg.trim().length < 3} onClick={send}>{busy ? "Sending…" : "Send request"}</Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          </div>
        </div>
      )}
    </section>
  );
}
