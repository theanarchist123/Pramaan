# ADR 0014: Generative certificate background (blueprint module 3)

Status: **accepted 2026-11-14 for an OFFLINE, generate-once-and-freeze library using FLUX.1 [schnell] on Cloudflare Workers AI. Built and run with real credentials; 59 pictures reviewed and approved across 15 sectors.** Live per-certificate generation is NOT built and not planned.

The blueprint asks for a unique generative background per certificate (it names Midjourney or Flux). Our rule says certificates use only frozen local images
(`AGENTS.md`). So pictures are generated once, a person reviews each, and the approved ones are frozen and used by certificates like the stock photos were.

## Decision
- **Model:** `@cf/black-forest-labs/flux-1-schnell` through Cloudflare Workers AI REST. **Not** Midjourney (no official API; reported to bar automated use) and **not**
  Gemini image models (reported to have no free API quota).
- **Library, not live generation:** about 14 sectors x a handful of pictures, made by `backend/scripts/cert_art.py`, reviewed on a contact sheet, approved by id.
  Each certificate picks one for its sector by its own digest, so every certificate is still unique (the per-certificate guilloche artwork is drawn on top, as before).
- **Why:** no daily limit or outage can ever affect issuing a certificate (I-2), no billing risk, and no vendor terms are exercised at request time.

## Verified facts (read 2026-11-14 from official sources)
- **Licence of the model:** the Hugging Face API (`huggingface.co/api/models/black-forest-labs/FLUX.1-schnell`) lists the licence tag `apache-2.0`. The model card
  itself is gated (login) so its text was not read.
- **Cloudflare model page** (`developers.cloudflare.com/workers-ai/models/flux-1-schnell/`): model id as above; input `prompt` (string, 1 to 2048 characters),
  `steps` (integer, maximum 8, default 4), optional `seed`; output `image` (base64 JPEG); "Zero data retention: Yes"; a "Terms and License" link.
- **Free allowance (Cloudflare pricing page, secondary sources for the arithmetic):** 10,000 neurons per day free; FLUX schnell is priced per 512x512 tile and per step.
  Roughly 100 to 230 small images a day; larger output costs more. Exceeding the free allowance on the Workers Free plan is reported to fail rather than bill: **confirm in your
  Cloudflare dashboard, and do not add a payment card.**

## Verified by a real run (2026-11-14, owner's free account, 4 pictures)
- The REST call works with a token holding **Workers AI Read + Edit** scoped to the account; the response envelope is parsed correctly and images come back at about 1024 px.
- The REST API **rejects a `seed` property** (HTTP 400 "Additional or unevaluated properties '/seed'"), unlike the Workers-binding example on the docs page. Only `prompt` and `steps` are sent.
- Cloudflare's **safety filter is fuzzy**: it refused an innocent prompt as "NSFW" while accepting near-identical wording. The tool treats that as retryable and tries up to two plainer wordings of the same motifs, recording the wording that worked.
- Output with the first style line was a circle on white; the style now asks for the pattern to fill the frame edge to edge, which gave full-bleed gold-and-indigo ornamental patterns (no faces, text, flags or religious imagery in the 3 reviewed; one 4-lobed shape could be read as a cross and is left to the human reviewer).

## Terms read 2026-11-14
- **Black Forest Labs Terms of Service** (`bfl.ai/legal/terms-of-service`, section 1.2 "Input and Output"): "We claim no ownership rights in and to Your Content" (Output is part of
  Your Content) and the user "may use Your Content in connection with the Services for your own purposes, subject to any restrictions set forth herein or under applicable law".
  The user is solely responsible for their content and its later use. Output does not include model weights. Other users may get similar output (no exclusivity).
  The terms bar exploiting the *Services* commercially, "except for your use of your Output", so use of Output is carved out. Caveat: these are BFL's own-service terms;
  we call the model through Cloudflare, and the model is tagged Apache-2.0 (which covers the weights, not a promise about copyright in the output).
- **Cloudflare:** the pages fetched (`cloudflare.com/website-terms/`, service-specific terms for application services) did not contain Workers AI output wording, and the
  actual "Terms and License" target from the model page was not opened. **Still unverified: Cloudflare's own text on ownership/use of Workers AI output.**
- Practical reading (not legal advice): we use abstract ornamental patterns as certificate backgrounds, no one else's content or likeness, with a human review of each.
  Nothing read forbids that, and the licence string on each certificate stays honest. A lawyer should confirm before any paid or large-scale use.

## NOT verified (do before relying on it)
- The Cloudflare Workers AI terms/licence text on generated output (see above). Open the "Terms and License" link in the model page in a browser and record it here.
- Free-allowance behaviour at the limit (the tool stops cleanly on HTTP 402/429 or a quota message, but a limit was not reached in testing). Do not add a payment card.

## Safeguards built in
- Prompts come only from Chitrakar's closed motif vocabulary plus a fixed style line, and are checked against the banned-word list (no faces, people, flags, logos, text,
  religious imagery) (I-3). Output is decoded and re-encoded to JPEG, so nothing hidden in the file survives.
- A **person** must look at every picture (`approve ... --reviewed`), and approval refuses a file that changed after it was generated.
- An approved asset's SHA-256 is recorded in `app/generated_art.json`, in `app/photo_manifest.json`, and in each certificate's **signed** art block with an honest source
  label (the licence string, not "Unsplash"). With no approved assets, certificates behave exactly as before.
- The API token is read only from `.env` (`CLOUDFLARE_API_TOKEN`), sent only in the Authorization header, never printed, and never used at request time.

## How to run it (owner)
1. Create a free Cloudflare account, create an API token with Workers AI access, and put `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` in your own `.env`.
2. `cd backend` then `.venv\Scripts\python scripts\cert_art.py generate --sector Science --count 4` (try one sector first), then `sheet`, look, `approve ID ... --reviewed`.
3. Commit `apps/web/public/certificate-photos/`, `app/photo_manifest.json` and `app/generated_art.json`.

## Sources
- <https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/> · <https://developers.cloudflare.com/workers-ai/platform/pricing/> · <https://huggingface.co/api/models/black-forest-labs/FLUX.1-schnell>
- Earlier secondary research (Midjourney API status, Gemini image free tier): see the previous version of this record in git history.
