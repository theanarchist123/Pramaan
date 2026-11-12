"use client";

import { useRef } from "react";
import { cleanChar, isCodeChar } from "@/lib/verify-verdict";
import { cn } from "@/lib/utils";

const LEN = 10;

/**
 * The certificate code PRM-XXXXXXXXXX as ten boxes: type or paste, it auto-advances, backspace steps back, and it submits when
 * the last character lands. Characters a code can never contain (0, 1, I, L, O, U) are refused with a quiet hint, not a shake.
 */
export function CodeInput({
  value,
  onChange,
  onComplete,
  onReject,
  bad,
}: {
  value: string;
  onChange: (v: string) => void;
  onComplete: (v: string) => void;
  /** Called with the first character that a code can never contain, so the page can explain why it was refused. */
  onReject: (ch: string) => void;
  bad: string;
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const chars = value.padEnd(LEN, " ").slice(0, LEN).split("");

  function setAt(i: number, raw: string) {
    const incoming = [...raw].map(cleanChar).join("").replace(/^PRM/, "");
    const accepted = [...incoming].filter(isCodeChar);
    const refused = [...incoming].find((ch) => !isCodeChar(ch));
    onReject(refused ?? ""); // clears the hint when everything typed was acceptable
    if (!accepted.length) return;
    const next = chars.map((c) => (c === " " ? "" : c));
    let pos = i;
    for (const ch of accepted) {
      if (pos >= LEN) break;
      next[pos++] = ch;
    }
    const joined = next.join("").slice(0, LEN);
    onChange(joined);
    refs.current[Math.min(pos, LEN - 1)]?.focus();
    if (joined.length === LEN && pos >= LEN) onComplete(`PRM-${joined}`);
  }

  return (
    <div role="group" aria-label="Certificate code" className="flex flex-wrap items-center gap-1.5">
      <span className="select-none font-mono text-lg text-muted-foreground" aria-hidden>
        PRM-
      </span>
      {chars.map((c, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          value={c.trim()}
          inputMode="text"
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
          aria-label={`Character ${i + 1} of ${LEN}`}
          maxLength={LEN}
          onChange={(e) => setAt(i, e.target.value)}
          onPaste={(e) => {
            e.preventDefault();
            setAt(0, e.clipboardData.getData("text"));
          }}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && !c.trim() && i > 0) {
              const next = chars.map((x) => x.trim());
              next[i - 1] = "";
              onChange(next.join("").replace(/\s+$/, ""));
              refs.current[i - 1]?.focus();
            }
            if (e.key === "Enter" && value.length === LEN) onComplete(`PRM-${value}`);
          }}
          className={cn(
            "size-10 rounded-md border bg-background text-center font-mono text-lg uppercase outline-none transition-colors focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/50",
            c.trim() ? "border-primary/60" : "border-input",
          )}
        />
      ))}
      <p className={cn("basis-full text-xs", bad ? "text-muted-foreground" : "sr-only")} aria-live="polite">
        {bad ? `"${bad}" never appears in a code (no 0, 1, I, L, O or U). Check the document.` : ""}
      </p>
    </div>
  );
}
