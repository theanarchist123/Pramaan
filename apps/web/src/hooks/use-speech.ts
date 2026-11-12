"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Web Speech API: free, keyless, runs in Chrome/Edge. Typing always remains available.
export const VOICE_LANGS = [
  { code: "en-IN", label: "English" },
  { code: "hi-IN", label: "हिन्दी" },
  { code: "mr-IN", label: "मराठी" },
  { code: "ta-IN", label: "தமிழ்" },
  { code: "te-IN", label: "తెలుగు" },
  { code: "bn-IN", label: "বাংলা" },
  { code: "gu-IN", label: "ગુજરાતી" },
  { code: "kn-IN", label: "ಕನ್ನಡ" },
] as const;

/* eslint-disable @typescript-eslint/no-explicit-any */
type Recognition = any;

function getRecognitionCtor(): (new () => Recognition) | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** What you said goes into the message box for you to check before sending (a misheard name must not be recorded as a fact). */
export function appendSpoken(existing: string, spoken: string): string {
  const s = spoken.trim();
  if (!s) return existing;
  const e = existing.trimEnd();
  return e ? `${e} ${s}` : s;
}

export function useSpeechInput(lang: string, onFinal: (text: string) => void) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const recRef = useRef<Recognition | null>(null);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  // The desktop shell (Electron) exposes the recognition API but ships no speech service, so it would fail at
  // runtime: hide the mic there and let people type.
  useEffect(() => {
    const desktop = Boolean((window as unknown as { pramaanDesktop?: { isDesktop?: boolean } }).pramaanDesktop?.isDesktop);
    setSupported(getRecognitionCtor() !== null && !desktop);
  }, []);

  const stop = useCallback(() => {
    recRef.current?.stop();
  }, []);

  const start = useCallback((local = true) => {
    const Ctor = getRecognitionCtor();
    if (!Ctor) return;
    recRef.current?.abort();
    const rec = new Ctor();
    rec.lang = lang;
    // Prefer on-device recognition where the browser offers it (MDN: SpeechRecognition.processLocally). Otherwise some browsers send the audio to
    // their maker's speech service, which the notice under the microphone says.
    if (local && "processLocally" in rec) rec.processLocally = true;
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (e: any) => {
      let finalText = "";
      let interimText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interimText += r[0].transcript;
      }
      setInterim(interimText);
      if (finalText.trim()) onFinalRef.current(finalText.trim());
    };
    rec.onend = () => {
      setListening(false);
      setInterim("");
    };
    rec.onerror = (e: any) => {
      setListening(false);
      setInterim("");
      // This language is not installed for on-device recognition: use the browser online service, which the notice already discloses.
      if (local && e?.error === "language-not-supported") setTimeout(() => start(false), 0);
    };
    recRef.current = rec;
    setListening(true);
    rec.start();
  }, [lang]);

  useEffect(() => () => recRef.current?.abort(), []);

  return { supported, listening, interim, start, stop };
}

export function speak(text: string, lang: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  u.rate = 0.98;
  window.speechSynthesis.speak(u);
}

export function stopSpeaking() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
}
