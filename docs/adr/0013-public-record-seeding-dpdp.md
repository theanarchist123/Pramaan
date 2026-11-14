# ADR 0013: Public-record seeding and "claim this profile" (DPDP review)

Status: **researched 2026-11-14 from secondary sources; NOT approved; seeding NOT built.** Needs a lawyer's reading of the Act itself.

## Decision made by the owner (2026-11-13)
Seed notable people from public records (Wikidata) as "public record, not yet claimed", each with a "This is me, claim it" flow.

## What the research found (law-firm and academic commentary, not the statute text; I did not read the Act itself)
- Section 3(c)(ii) of the Digital Personal Data Protection Act 2023 is reported to exclude personal data that was made publicly available **by the person it is about**, or by someone **under a legal obligation** to publish it.
- "Publicly available" is not defined, and commentators say the Rules (2025) do not clarify it. Several advise against assuming that anything found online qualifies, and say the source must be checked.
- Wikidata entries are written by volunteers, not by the person concerned and not under a legal duty. **So the exclusion probably does NOT cover Wikidata-sourced profiles**, which means republishing them would be processing that the Act does cover (lawful basis, notice, purpose limits, erasure on request).
- Timing reported: the DPDP Rules were notified 13-14 November 2025; consent-manager rules from about November 2026; most substantive duties from about May 2027. Sources differ slightly on dates.
- Not settled in the sources: whether aggregating or enriching public data removes the exclusion.

## Consequence for the plan (recommendation, not legal advice)
Do not seed from Wikidata until a lawyer has read the Act and the Rules and confirmed a basis. The safer path that needs no such judgement is **invitation with consent**: staff or the owner invite specific notable people (their own email), who confirm and verify their own profile. That reuses what is already built (onboarding, review, certificate) and needs no `public_records` table.

## Design constraints if seeding is ever approved
- Separate `public_records` table, never a `Profile` without an owner (I-5, I-10); minimal fields; source and date shown; a visible removal request honoured before the next index rebuild; a claim creates a normal profile that goes through normal verification.

## Sources consulted (secondary)
- <https://law.asia/publicly-available-data-dpdpa/> · <https://lawschoolpolicyreview.com/2026/01/13/publicly-available-data-under-the-dpdp-act-the-limits-of-exemptions-in-ai-driven-processing/> · <https://iapp.org/news/a/scraping-public-data-in-india-innovation-enabler-or-privacy-threat-> · <https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/> · <https://dpdpa.com/dpdpa2023/chapter-1/section3.html> (statute text, not read)
