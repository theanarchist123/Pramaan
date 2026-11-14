"use client";

import { useEffect, useState } from "react";
import { Copy, Share2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

/** WhatsApp glyph (lucide has no brand icons). */
function WhatsAppIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={cn("size-4", className)} fill="currentColor">
      <path d="M12 2a10 10 0 00-8.6 15.1L2 22l5-1.3A10 10 0 1012 2zm0 18.2a8.2 8.2 0 01-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1112 20.2zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8s-.4-.1-.6.1-.7.8-.8 1-.3.2-.5.1a6.7 6.7 0 01-3.3-2.9c-.2-.4.2-.4.7-1.3a.5.5 0 000-.5c-.1-.1-.6-1.4-.8-1.9s-.4-.4-.6-.4h-.5a1 1 0 00-.7.3 3 3 0 00-.9 2.2 5.2 5.2 0 001.1 2.8 11.9 11.9 0 004.6 4.1c1.7.7 2.4.8 3.2.7a2.7 2.7 0 001.8-1.3 2.2 2.2 0 00.2-1.3c-.1-.1-.3-.2-.5-.3z" />
    </svg>
  );
}

const pill =
  "inline-flex h-10 items-center gap-2 rounded-full border-2 border-foreground px-4 text-sm font-semibold transition-transform hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2";

/**
 * Share a public page. WhatsApp first (the way most people in India pass things on), the device's own share sheet when it has one,
 * and a copy-link fallback. The link is always the public page's address; no private data is placed in the message.
 */
export function ShareRow({ url, text, className }: { url?: string; text: string; className?: string }) {
  const [href, setHref] = useState(url ?? "");
  const [canShare, setCanShare] = useState(false);
  useEffect(() => {
    if (!url) setHref(window.location.href);
    setCanShare(typeof navigator !== "undefined" && typeof navigator.share === "function");
  }, [url]);

  const wa = `https://wa.me/?text=${encodeURIComponent(`${text} ${href}`.trim())}`;
  const copy = () => {
    navigator.clipboard.writeText(href).then(
      () => toast.success("Link copied"),
      () => toast.error("Couldn't copy. Select the address bar instead."),
    );
  };

  return (
    <div className={cn("flex flex-wrap gap-2", className)} role="group" aria-label="Share">
      <a href={wa} target="_blank" rel="noreferrer noopener" className={pill}>
        <WhatsAppIcon /> WhatsApp
      </a>
      {canShare && (
        <button type="button" className={pill} onClick={() => navigator.share({ title: text, url: href }).catch(() => {})}>
          <Share2 className="size-4" /> Share
        </button>
      )}
      <button type="button" className={pill} onClick={copy}>
        <Copy className="size-4" /> Copy link
      </button>
    </div>
  );
}
