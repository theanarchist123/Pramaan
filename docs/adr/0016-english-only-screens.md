# ADR 0016: Screens are English only for now

Status: **accepted 2026-11-19 (owner decision).** Supersedes the "Hindi copy is written natively and reviewed" line in AGENTS.md for the time being.

## Decision
- Every screen is shown in English. The language switcher is hidden on desktop and on phone, and a language saved by an earlier visit is ignored.
- One constant, `HINDI_UI_ENABLED` in `apps/web/src/lib/i18n.tsx`, turns the Hindi screens back on. The Hindi dictionary stays in the code, unused.
- **Typing or speaking Hindi (or any language) still works** in search and in the Saathi chat. The model understands the person; that needs no translated screens
  and no copy review.

## Why
- The first users are people who already use English on the web. Someone who cannot read English will not get through document verification either.
- Hindi screens on a trust product need a native reader. `docs/review/hindi-copy-review.md` is still unsigned, and a wrong word on a "revoked" or "verified" screen is
  worse than English.
- Every new screen would need a translation and a review, which slows a product that needs to change weekly.

## What brings Hindi back
A native Hindi reader signs off `docs/review/hindi-copy-review.md`, or users ask for it. Then set `HINDI_UI_ENABLED = true`, re-run `pnpm lint && pnpm build`, and
re-check the phone audit (Devanagari lines are taller).
