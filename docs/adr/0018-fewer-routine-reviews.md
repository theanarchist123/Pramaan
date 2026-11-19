# ADR 0018: Fewer routine reviews

Status: **accepted 2026-11-19 (owner decision: a person looking at every profile is too slow for a product that should be usable by many people).**

## What changed
- `human_approval_first_listing` now defaults to **off**. Before, every owner's first public listing went to a person even when everything checked out.
- Unchanged, deliberately:
  - **Anyone without a matching document still goes to a person** ("Identity not confirmed by a matching document"). That is a separate rule in Prahari and is the
    reason people with no evidence still wait.
  - **Award claims still go to a person** (`award_claims_need_human`). The setting's own comment says to turn that off only once issuers are checked at the source
    (for example DigiLocker or an official award list), and we do not do that yet.
  - Forged-looking documents, name mismatches, contradicted claims, common names with no second detail, and every error still go to a person (I-1, I-2).
- Both remain **governed settings**: switching either one needs a second person's approval and leaves a history.

## Why not a blockchain
A blockchain proves a record has not changed since it was written. Certificates already have that (signed, in a public hash-chained log). It cannot show a claim was
true when written, so it does not replace evidence or review.

## What would remove more reviews (not done; needs a product decision)
1. Label instead of block: publish people without documents with every claim labelled "self-declared". This changes what "verified registry" means on the site (the
   directory says "Only verified, consenting people appear") and needs a change in `agents/prahari.py` (an always-human-review file).
2. Check at the source: DigiLocker, official award lists, ORCID, institution confirmation by email. A match raises the label with no person involved.
3. Keep people for exceptions only: reports, forged documents, very high-stakes claims, and a small weekly sample.

## How to undo
`human_approval_first_listing=true` through a governed-setting change (second person approves), or by environment variable.
