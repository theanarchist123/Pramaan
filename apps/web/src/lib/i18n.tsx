"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Lang = "en" | "hi";
const KEY = "pramaan.lang";

/**
 * UI strings for the highest-traffic screens in English and Hindi. (Conversations with Saathi and
 * search queries already work in any language — this translates the interface around them.)
 * A missing Hindi string falls back to English, never to a blank.
 */
const en = {
  "nav.directory": "Directory", "nav.verify": "Verify", "nav.mission": "Mission Control",
  "nav.developers": "Developers", "nav.admin": "Admin", "nav.search": "Search", "nav.signin": "Sign in",
  "nav.signout": "Sign out", "nav.menu": "Open menu", "nav.largeText": "Toggle large text",
  "nav.darkMode": "Toggle dark mode", "nav.language": "Switch language", "nav.skip": "Skip to content",

  "home.badge": "Who's Who India — rebuilt around evidence",
  "home.h1a": "Don't claim it.", "home.h1b": "Prove it.",
  "home.lead": "Pramaan is a registry of notable people in India where every achievement carries its evidence, a team of AI agents does the paperwork, and every certificate can be verified by anyone, anywhere.",
  "home.cta1": "Create my verified profile", "home.cta2": "Verify a certificate",
  "home.hint": "About 3 minutes. Voice or text. Your data, your consent.",
  "home.how": "How a claim becomes proof",
  "home.step": "Step",
  "home.s1t": "Just talk", "home.s1b": "Speak or type in Hindi, English, Marathi, Tamil — Saathi builds your profile live. No forms.",
  "home.s2t": "Agents gather proof", "home.s2b": "Every claim is checked against public sources and your documents. Quotes are verified word-for-word.",
  "home.s3t": "A human signs off on doubt", "home.s3b": "Below 95% confidence, Prahari stops and hands it to a reviewer — with the reasons.",
  "home.s4t": "Proof anyone can check", "home.s4b": "A signed certificate with unique generative art. Scan the QR — or try to tamper with it.",
  "home.teamH": "Meet the team doing the paperwork",
  "home.teamP": "Ten specialised agents, each replacing a manual job. You can watch every one of them work, live, in Mission Control.",
  "home.openMission": "Open Mission Control",
  "home.footer": "Pramaan · Built AI-native. Public verification needs no account — certificates are signed with Ed25519 and logged in a public hash chain.",
  "home.verifiedProfiles": "Verified profiles", "home.signedCerts": "Signed certificates",

  "consent.title": "Let's build your verified profile",
  "consent.sub": "No forms. You talk, Saathi listens. Then our agents gather the evidence.",
  "consent.nameLabel": "Your full name", "consent.optional": "(optional)",
  "consent.nameHint": "If you're publicly known, we can find you and pre-fill your profile — you just confirm.",
  "consent.legend": "Your consent",
  "consent.listingB": "List my verified profile publicly.",
  "consent.listingR": "Required to be in the registry. You can export or delete your data any time.",
  "consent.researchB": "Look me up in public sources.",
  "consent.researchR": "Used only to pre-fill and verify your claims. Everything found is shown to you first.",
  "consent.start": "Start talking to Saathi", "consent.starting": "Starting…",

  "chat.subtitle": "Your interviewer · speaks your language",
  "chat.placeholder": "Type or tap the mic to speak…", "chat.listening": "Listening…",
  "chat.send": "Send", "chat.message": "Your message", "chat.speak": "Speak your answer", "chat.stop": "Stop listening",

  "verify.title": "Verify a certificate",
  "verify.sub": "Scan the QR code on any Pramaan certificate, or type its code below. No account needed.",
  "verify.codeLabel": "Certificate code", "verify.button": "Verify",
  "verify.authentic": "Authentic certificate", "verify.revoked": "Certificate revoked", "verify.cannot": "Cannot be verified",
  "verify.how": "How we checked", "verify.keep": "Keep it, share it", "verify.forge": "Try to forge it",
  "verify.yourself": "Don't trust us — verify it yourself",

  "dir.title": "The registry",
  "dir.sub": "Ask in plain English, in any language. Only verified, consenting people appear — and every result says why.",
  "dir.placeholder": "e.g. clean-energy innovators in Karnataka who collaborated with universities",
  "dir.search": "Search the registry", "dir.searchBtn": "Search", "dir.people": "People", "dir.network": "Network",
  "dir.map": "Map", "dir.clear": "Clear filters", "dir.allStates": "All states",
  "dir.none": "No one matches yet.", "dir.noneHint": "Try a broader question, or clear the filters.",
} as const;

export type Key = keyof typeof en;

const hi: Partial<Record<Key, string>> = {
  "nav.directory": "निर्देशिका", "nav.verify": "सत्यापन", "nav.mission": "मिशन कंट्रोल",
  "nav.developers": "डेवलपर्स", "nav.admin": "एडमिन", "nav.search": "खोजें", "nav.signin": "साइन इन",
  "nav.signout": "साइन आउट", "nav.menu": "मेनू खोलें", "nav.largeText": "बड़े अक्षर चालू/बंद करें",
  "nav.darkMode": "डार्क मोड चालू/बंद करें", "nav.language": "भाषा बदलें", "nav.skip": "सीधे सामग्री पर जाएँ",

  "home.badge": "भारत के जाने-माने लोग — अब सबूतों के साथ",
  "home.h1a": "दावा मत कीजिए।", "home.h1b": "साबित कीजिए।",
  "home.lead": "प्रमाण भारत के जाने-माने लोगों की एक रजिस्ट्री है, जहाँ हर उपलब्धि के साथ उसका सबूत होता है, AI एजेंटों की एक टीम सारा काग़ज़ी काम करती है, और हर प्रमाणपत्र को कोई भी, कहीं भी सत्यापित कर सकता है।",
  "home.cta1": "मेरा सत्यापित प्रोफ़ाइल बनाएँ", "home.cta2": "प्रमाणपत्र सत्यापित करें",
  "home.hint": "लगभग 3 मिनट। बोलकर या लिखकर। आपका डेटा, आपकी सहमति।",
  "home.how": "कोई दावा प्रमाण कैसे बनता है",
  "home.step": "चरण",
  "home.s1t": "बस बोलिए", "home.s1b": "हिंदी, अंग्रेज़ी, मराठी, तमिल — जिसमें चाहें बोलें या लिखें। साथी आपका प्रोफ़ाइल उसी समय बनाता है। कोई फ़ॉर्म नहीं।",
  "home.s2t": "एजेंट सबूत जुटाते हैं", "home.s2b": "हर दावे को सार्वजनिक स्रोतों और आपके दस्तावेज़ों से परखा जाता है। उद्धरण शब्दशः जाँचे जाते हैं।",
  "home.s3t": "संदेह होने पर इंसान फ़ैसला करता है", "home.s3b": "95% से कम भरोसा होने पर प्रहरी रुक जाता है और कारण सहित समीक्षक को सौंप देता है।",
  "home.s4t": "ऐसा सबूत जिसे कोई भी जाँच सके", "home.s4b": "अनोखी जनरेटिव कला वाला हस्ताक्षरित प्रमाणपत्र। QR स्कैन कीजिए — या उसमें जालसाज़ी करके देखिए।",
  "home.teamH": "काग़ज़ी काम करने वाली टीम से मिलिए",
  "home.teamP": "दस विशेष एजेंट, जिनमें से हर एक किसी हाथ के काम की जगह लेता है। आप मिशन कंट्रोल में उन सबको लाइव काम करते देख सकते हैं।",
  "home.openMission": "मिशन कंट्रोल खोलें",
  "home.footer": "प्रमाण · AI-नेटिव। सार्वजनिक सत्यापन के लिए खाते की ज़रूरत नहीं — प्रमाणपत्र Ed25519 से हस्ताक्षरित हैं और एक सार्वजनिक हैश-श्रृंखला में दर्ज हैं।",
  "home.verifiedProfiles": "सत्यापित प्रोफ़ाइल", "home.signedCerts": "हस्ताक्षरित प्रमाणपत्र",

  "consent.title": "आइए आपका सत्यापित प्रोफ़ाइल बनाएँ",
  "consent.sub": "कोई फ़ॉर्म नहीं। आप बोलिए, साथी सुनता है। फिर हमारे एजेंट सबूत जुटाते हैं।",
  "consent.nameLabel": "आपका पूरा नाम", "consent.optional": "(वैकल्पिक)",
  "consent.nameHint": "यदि आप सार्वजनिक रूप से जाने जाते हैं, तो हम आपको ढूँढकर प्रोफ़ाइल पहले से भर सकते हैं — आपको बस पुष्टि करनी है।",
  "consent.legend": "आपकी सहमति",
  "consent.listingB": "मेरा सत्यापित प्रोफ़ाइल सार्वजनिक रूप से दिखाएँ।",
  "consent.listingR": "रजिस्ट्री में आने के लिए ज़रूरी। आप कभी भी अपना डेटा निकाल या मिटा सकते हैं।",
  "consent.researchB": "सार्वजनिक स्रोतों में मुझे खोजें।",
  "consent.researchR": "सिर्फ़ प्रोफ़ाइल भरने और दावों को परखने के लिए। जो कुछ मिलेगा, पहले आपको दिखाया जाएगा।",
  "consent.start": "साथी से बात शुरू करें", "consent.starting": "शुरू हो रहा है…",

  "chat.subtitle": "आपका इंटरव्यूअर · आपकी भाषा में बात करता है",
  "chat.placeholder": "लिखिए, या बोलने के लिए माइक दबाइए…", "chat.listening": "सुन रहा हूँ…",
  "chat.send": "भेजें", "chat.message": "आपका संदेश", "chat.speak": "बोलकर जवाब दीजिए", "chat.stop": "सुनना बंद करें",

  "verify.title": "प्रमाणपत्र सत्यापित करें",
  "verify.sub": "किसी भी प्रमाण प्रमाणपत्र का QR कोड स्कैन कीजिए, या उसका कोड नीचे लिखिए। खाते की ज़रूरत नहीं।",
  "verify.codeLabel": "प्रमाणपत्र कोड", "verify.button": "सत्यापित करें",
  "verify.authentic": "प्रामाणिक प्रमाणपत्र", "verify.revoked": "प्रमाणपत्र रद्द किया गया", "verify.cannot": "सत्यापित नहीं हो सका",
  "verify.how": "हमने कैसे जाँचा", "verify.keep": "सहेजिए, साझा कीजिए", "verify.forge": "जालसाज़ी करके देखिए",
  "verify.yourself": "हम पर भरोसा मत कीजिए — ख़ुद सत्यापित कीजिए",

  "dir.title": "रजिस्ट्री",
  "dir.sub": "सरल भाषा में, किसी भी भाषा में पूछिए। सिर्फ़ सत्यापित और सहमत लोग दिखते हैं — और हर नतीजा बताता है कि क्यों।",
  "dir.placeholder": "जैसे: कर्नाटक में स्वच्छ ऊर्जा के नवप्रवर्तक जिन्होंने विश्वविद्यालयों के साथ काम किया",
  "dir.search": "रजिस्ट्री में खोजें", "dir.searchBtn": "खोजें", "dir.people": "लोग", "dir.network": "नेटवर्क",
  "dir.map": "नक्शा", "dir.clear": "फ़िल्टर हटाएँ", "dir.allStates": "सभी राज्य",
  "dir.none": "अभी कोई मेल नहीं खाता।", "dir.noneHint": "कोई व्यापक सवाल आज़माएँ, या फ़िल्टर हटाएँ।",
};

const DICTS: Record<Lang, Partial<Record<Key, string>>> = { en, hi };

interface I18n {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: Key) => string;
}
const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(KEY);
    } catch {
      /* storage blocked: fall back to the browser's language */
    }
    setLangState(saved === "hi" || saved === "en" ? saved : navigator.language?.toLowerCase().startsWith("hi") ? "hi" : "en");
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang; // screen readers pick the right voice
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* per-viewer convenience only */
    }
  }, []);

  const value = useMemo<I18n>(
    () => ({ lang, setLang, t: (key) => DICTS[lang][key] ?? en[key] }),
    [lang, setLang],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const c = useContext(Ctx);
  if (!c) throw new Error("useI18n must be used inside <I18nProvider>");
  return c;
}

/** The speech-recognition locale that matches the interface language. */
export const speechLocale = (lang: Lang) => (lang === "hi" ? "hi-IN" : "en-IN");
