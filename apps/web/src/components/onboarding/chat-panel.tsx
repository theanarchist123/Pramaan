"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Mic, MicOff, SendHorizontal, Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AgentAvatar } from "@/components/agent-feed";
import { VOICE_LANGS, speak, stopSpeaking, useSpeechInput } from "@/hooks/use-speech";
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
}: {
  messages: ChatMessage[];
  thinking: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onSend: (text: string) => void;
  header?: React.ReactNode;
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
  const lastSpoken = useRef(0);

  const { supported, listening, interim, start, stop } = useSpeechInput(lang, (spoken) => {
    // Voice-first: what you say is sent straight away, like talking to a person.
    onSend(spoken);
  });

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

  function submit() {
    const t = text.trim();
    if (!t || disabled || thinking) return;
    onSend(t);
    setText("");
  }

  return (
    <section className="flex h-full min-h-0 flex-col" aria-label="Conversation with Saathi">
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <AgentAvatar name="Saathi" className="size-9 text-sm" />
        <div className="min-w-0 flex-1">
          <p className="font-medium">Saathi</p>
          <p className="text-xs text-muted-foreground">{t("chat.subtitle")}</p>
        </div>
        <label className="sr-only" htmlFor="voice-lang">Voice language</label>
        <select
          id="voice-lang"
          value={lang}
          onChange={(e) => {
            setLangChosen(true);
            setLang(e.target.value);
          }}
          className="h-8 rounded-md border border-input bg-background px-2 text-sm"
        >
          {VOICE_LANGS.map((l) => (
            <option key={l.code} value={l.code}>{l.label}</option>
          ))}
        </select>
        <Button
          variant="ghost"
          size="icon"
          aria-pressed={voiceOut}
          aria-label={voiceOut ? "Stop reading replies aloud" : "Read replies aloud"}
          onClick={() => {
            if (voiceOut) stopSpeaking();
            setVoiceOut(!voiceOut);
          }}
        >
          {voiceOut ? <Volume2 /> : <VolumeX />}
        </Button>
      </div>

      {header}

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn("flex gap-2", m.role === "user" && "justify-end")}
            >
              {m.role === "assistant" && <AgentAvatar name="Saathi" />}
              <p
                className={cn(
                  "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-[15px] leading-relaxed",
                  m.role === "assistant"
                    ? "rounded-tl-sm bg-muted"
                    : "rounded-tr-sm bg-primary text-primary-foreground",
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
          <div className={cn("flex gap-2", interim && "justify-end")}>
            {interim ? (
              <p className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary/40 px-3.5 py-2.5 text-[15px] italic">
                {interim}…
              </p>
            ) : (
              <>
                <AgentAvatar name="Saathi" />
                <span className="flex items-center gap-1 rounded-2xl rounded-tl-sm bg-muted px-4 py-3" aria-label="Saathi is typing">
                  {[0, 1, 2].map((d) => (
                    <motion.span
                      key={d}
                      className="size-1.5 rounded-full bg-muted-foreground"
                      animate={{ opacity: [0.3, 1, 0.3] }}
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

      <div className="border-t border-border p-3">
        {disabled ? (
          <p className="py-2 text-center text-sm text-muted-foreground">{disabledReason}</p>
        ) : (
          <div className="flex items-end gap-2">
            {supported && (
              <Button
                type="button"
                size="icon-lg"
                variant={listening ? "default" : "outline"}
                className={cn("size-11 rounded-full", listening && "animate-pulse")}
                aria-label={listening ? t("chat.stop") : t("chat.speak")}
                onClick={listening ? stop : start}
              >
                {listening ? <MicOff /> : <Mic />}
              </Button>
            )}
            <Textarea
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
              className="max-h-40 min-h-11 resize-none text-[15px]"
              aria-label={t("chat.message")}
            />
            <Button
              type="button"
              size="icon-lg"
              className="size-11 rounded-full"
              disabled={!text.trim() || thinking}
              aria-label={t("chat.send")}
              onClick={submit}
            >
              <SendHorizontal />
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
