# ADR 0011: Saathi voice, confirmation and multilingual evaluation (AGT-11)

Status: accepted (2026-11-12).

## Voice (browser Web Speech API; checked at developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition, read 2026-11-12)
- The API is "limited availability": not Baseline. Chrome and Edge 139+, Safari 14.1+ (prefixed), Firefox 160+; **not Firefox for Android**. Typing always remains.
- **Privacy:** MDN notes that in some browsers, like Chrome, speech recognition uses a server-based engine and the audio is sent to a web service. So: the chat shows that notice under the microphone (English and Hindi; the Hindi wording needs a native-speaker review), and `processLocally` (on-device recognition, Chrome and Edge 139+, Firefox 160+) is requested first, falling back to the online service only when the language pack is not installed.
- **Confirmation:** what is spoken now lands in the message box for the person to read and send. It used to be sent immediately, which could record a misheard name as a fact.
- Read-aloud (speech synthesis) and per-language voice choice already existed; the desktop shell hides the microphone because Electron ships no speech service.

## Coverage
Onboarding "ready to submit" and the progress score are counted by code, not by the model (`services/onboarding.coverage`).

## Multilingual evaluation (`python -m evals.saathi_eval [--live]`, 12 fictional cases, 1-4 per language: indicative only)
One live run on 2026-11-12 (Gemini with provider fallbacks; two models were briefly unavailable and fell back): English 4/4 on name, state and field. State was right in every language.
**Names in Devanagari, Marathi, Tamil and Bengali scored 0**: the model most likely writes them in Latin letters instead of copying them, so the recorded name differs from what was said.
Hinglish field (sector) was wrong in both cases. **Owner decision needed**: should the registry keep a person's name in the script they used? If yes, the Saathi prompt and `apply_delta` must preserve it and the eval must pass before release.
The offline mock only checks the plumbing (it cannot read Hindi).

## Not done
- The Hindi notice and any other Hindi copy have not been reviewed by a native speaker.
- No larger multilingual golden set, and no live run on the nightly workflow for Saathi yet (`evals/saathi_eval.py --live` is the command to add).
