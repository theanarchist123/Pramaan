"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

export function CopyButton({ text, label = "Copy", className }: { text: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(text).then(() => {
          setDone(true);
          setTimeout(() => setDone(false), 1600);
        });
      }}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-border bg-background/80 px-2 py-1 text-xs text-muted-foreground backdrop-blur transition-colors hover:text-foreground",
        className,
      )}
      aria-label={done ? "Copied" : `${label} to clipboard`}
    >
      {done ? <Check className="size-3.5 text-verified" /> : <Copy className="size-3.5" />} {done ? "Copied" : label}
    </button>
  );
}

export function CodeBlock({ code, language, className }: { code: string; language?: string; className?: string }) {
  return (
    <div className={cn("group relative", className)}>
      <pre className="overflow-x-auto rounded-xl bg-foreground p-4 text-[12.5px] leading-relaxed text-background" tabIndex={0}>
        <code>{code}</code>
      </pre>
      <div className="absolute right-2 top-2 flex items-center gap-2">
        {language && <span className="rounded bg-background/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-background/80">{language}</span>}
        <CopyButton text={code} />
      </div>
    </div>
  );
}
