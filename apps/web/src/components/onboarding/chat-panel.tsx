"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Mic, MicOff, SendHorizontal, Volume2, VolumeX } from "lucide-react";
import { SaathiMascot } from "@/components/onboarding/saathi-mascot";
import { VOICE_LANGS, appendSpoken, speak, stopSpeaking, useSpeechInput } from "@/hooks/use-speech";
import { speechLocale, useI18n } from "@/lib/i18n";
import { markCaptured } from "@/lib/fact-capture";
import { cn } from "@/lib/utils";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  /** Exact quotes of the facts the registry recorded from this message (fact capture, M-03). */
  captured?: string[];
}

export function ChatPanel({
  messages,
  thinking,
  disabled,
  disabledReason,
  onSend,
  header,
  onListeningChange,
}: {
  messages: ChatMessage[];
  thinking: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onSend: (text: string) => void;
  header?: React.ReactNode;
  /** Lets the page show Saathi listening while the microphone is on. */
  onListeningChange?: (listening: boolean) => void;
}) {
  const [text, setText] = useState("");
  const { t, lang: uiLang } = useI18n();
  const [lang, setLang] = useState<string>(speechLocale(uiLang));
  // Follow the interface language until the person picks a voice language themselves.
  const [langChosen, setLangChosen] = useState(false);
  useEffect(() => {
    if (!langChosen) setLang(speechLocale(uiLang));
  }, [uiLang, langChosen]);
  const [voiceOut, setVoiceOut] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const lastSpoken = useRef(0);

  const { supported, listening, interim, start, stop } = useSpeechInput(lang, (spoken) => {
    // What you say lands in the box for you to read and send: speech recognition mishears names, and a misheard fact must not be recorded.
    setText((prev) => appendSpoken(prev, spoken));
  });

  useEffect(() => {
    onListeningChange?.(listening);
  }, [listening, onListeningChange]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, thinking, interim]);

  // Read Saathi's replies aloud when voice output is on.
  useEffect(() => {
    if (!voiceOut) return;
    const last = messages[messages.length - 1];
    if (last?.role === "assistant" && messages.length > lastSpoken.current) {
      lastSpoken.current = messages.length;
      speak(last.content, lang);
    }
  }, [messages, voiceOut, lang]);

  // Grow the box to fit the text (up to about six lines); a scrollbar appears only beyond that.
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    const h = Math.min(el.scrollHeight, 150);
    el.style.height = `${h}px`;
    el.style.overflowY = el.scrollHeight > 150 ? "auto" : "hidden";
  }, [text]);

  function submit() {
    const t = text.trim();
    if (!t || disabled || thinking) return;
    onSend(t);
    setText("");
  }

  return (
    <section className="flex h-full min-h-0 flex-col" aria-label="Conversation with Saathi">
      <div className="flex items-center justify-end gap-1 px-4 pt-3">
        <label className="sr-only" htmlFor="voice-lang">Voice language</label>
        <select
          id="voice-lang"
          value={lang}
          onChange={(e) => {
            setLangChosen(true);
            setLang(e.target.value);
          }}
          className="h-8 rounded-full border border-input bg-background px-3 text-sm"
        >
          {VOICE_LANGS.map((l) => (
            <option key={l.code} value={l.code}>{l.label}</option>
          ))}
        </select>
        <button
          type="button"
          aria-pressed={voiceOut}
          aria-label={voiceOut ? "Stop reading replies aloud" : "Read replies aloud"}
          className="inline-flex size-8 items-center justify-center rounded-full hover:bg-muted"
          onClick={() => {
            if (voiceOut) stopSpeaking();
            setVoiceOut(!voiceOut);
          }}
        >
          {voiceOut ? <Volume2 className="size-4" /> : <VolumeX className="size-4" />}
        </button>
      </div>

      {header}

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              className={cn("flex items-end gap-2.5", m.role === "user" && "justify-end")}
            >
              {m.role === "assistant" && <SaathiMascot size={34} still className="shrink-0" />}
              <p
                className={cn(
                  "max-w-[85%] whitespace-pre-wrap rounded-[1.4rem] px-4 py-3 text-base leading-relaxed",
                  m.role === "assistant"
                    ? "rounded-bl-md bg-muted"
                    : "rounded-br-md bg-primary font-medium text-primary-foreground",
                )}
              >
                {m.role === "user" && m.captured?.length
                  ? markCaptured(m.content, m.captured).map((seg, k) =>
                      seg.captured ? (
                        <mark
                          key={k}
                          className="rounded-sm bg-primary-foreground/25 px-0.5 text-inherit underline decoration-2 underline-offset-4 transition-colors duration-700 motion-reduce:transition-none"
                        >
                          {seg.text}
                          <span className="sr-only"> (recorded on your profile)</span>
                        </mark>
                      ) : (
                        <span key={k}>{seg.text}</span>
                      ),
                    )
                  : m.content}
              </p>
            </motion.div>
          ))}
        </AnimatePresence>
        {(thinking || interim) && (
          <div className={cn("flex items-end gap-2.5", interim && "justify-end")}>
            {interim ? (
              <p className="max-w-[85%] rounded-[1.4rem] rounded-br-md bg-primary/40 px-4 py-3 text-base italic">
                {interim}…
              </p>
            ) : (
              <>
                <SaathiMascot size={34} still state="thinking" className="shrink-0" />
                <span className="flex items-center gap-1.5 rounded-[1.4rem] rounded-bl-md bg-muted px-4 py-4" aria-label="Saathi is typing">
                  {[0, 1, 2].map((d) => (
                    <motion.span
                      key={d}
                      className="size-2 rounded-full bg-muted-foreground"
                      animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
                      transition={{ duration: 1, repeat: Infinity, delay: d * 0.15 }}
                    />
                  ))}
                </span>
              </>
            )}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="p-3">
        {disabled ? (
          <p className="rounded-2xl bg-muted px-4 py-3 text-center text-sm text-muted-foreground">{disabledReason}</p>
        ) : (
          <div className="flex items-end gap-2 rounded-[1.7rem] border-2 border-foreground/80 bg-background p-2 focus-within:border-[var(--brand)]">
            {supported && (
              <button
                type="button"
                className={cn(
                  "inline-flex size-11 shrink-0 items-center justify-center rounded-full border-2 border-foreground/80 transition-colors",
                  listening ? "animate-pulse bg-[var(--brand)] text-[var(--on-brand)]" : "hover:bg-muted",
                )}
                aria-label={listening ? t("chat.stop") : t("chat.speak")}
                aria-pressed={listening}
                onClick={listening ? stop : () => start()}
              >
                {listening ? <MicOff /> : <Mic />}
              </button>
            )}
            <textarea
              id="chat-input"
              ref={box}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder={listening ? t("chat.listening") : t("chat.placeholder")}
              rows={1}
              className="min-h-11 flex-1 resize-none overflow-hidden bg-transparent px-2 py-2.5 text-base leading-6 outline-none placeholder:text-muted-foreground"
              aria-label={t("chat.message")}
            />
            <button
              type="button"
              className="inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform hover:-translate-y-0.5 disabled:opacity-40"
              disabled={!text.trim() || thinking}
              aria-label={t("chat.send")}
              onClick={submit}
            >
              <SendHorizontal />
            </button>
          </div>
        )}
        {supported && !disabled && <p className="mt-1.5 px-2 text-xs text-muted-foreground">{t("chat.voice_note")}</p>}
      </div>
    </section>
  );
}
