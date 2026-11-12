# ADR 0004: DigiLocker as a source of issuer-signed documents (TRU-05, feasibility spike)

Status: **spike complete; integration deliberately not built yet.** Date: 2026-11-12.
AGENTS.md requires every "(verify)" item about the outside world to be checked against the official source and recorded before it is relied on.

## What was read (official sources, 2026-11-12)

| Source | What it says |
|---|---|
| DigiLocker partner FAQ, `digilocker.gov.in/web/partners/partner-faq` | Organisations register on the partner portal (`partners.apisetu.gov.in`) **by signing in with a DigiLocker account**, then apply to onboard as an **Issuer** or a **Requester** ("to access and verify documents or data, subject to applicable permissions"). Depending on category, an applicant must submit **a valid use case and onboarding documents: Proof of Identity, Authority Letter, Organization PAN, GST Registration Certificate, Certificate of Incorporation, etc.** After review the onboarding team "will facilitate API subscription, provide the necessary credentials". Approval and integration timelines "may vary". |
| Same FAQ | The APIs use **OAuth 2.0 with OpenID Connect**; access tokens are issued "after successful user authentication and consent". Issued documents are "digitally verifiable" and "carry the same legal validity as their physical counterparts". |
| DigiLocker onboarding FAQ (PDF) | Register on API Setu. A firm outside India needs a **registered Indian mobile number and a server located in India**. The callback URL should be the organisation's website so users return after consent. |
| DigiLocker requester page | Requesters integrate the published API specification (API Setu directory). |

## Not stated by those sources (so NOT assumed)
- Whether a **private registry like Pramaan is eligible** as a Requester (categories and eligibility rules are not published on the pages read).
- **Fees.**
- **Sandbox vs production steps**, and any test credentials.
- Any **limit on storing or reusing** a fetched document, and how the DPDP Act applies to a registry that keeps the extracted claim.
- Which issuers publish **academic and award credentials** in a form a registry can read (the pages list government documents; whether a given university or honours body is an Issuer on DigiLocker was not established).

## Decision
1. **Do not build the integration now.** It cannot work without partner approval, which needs a legal entity (PAN, GST, incorporation) and an approved use case. Building against an API we cannot call would produce untested code, which this project does not ship.
2. **Keep the seam ready.** The `issuer` claim status already exists end to end (certificate, VC, UI, I-8/I-9). A DigiLocker pull would create the evidence record kind `issuer` and nothing else: a consented fetch of an issuer-signed document, verified, stored as evidence, never an Aadhaar number or image (AGENTS.md; Aadhaar is out of scope).
3. **Next steps are the owner's, not the code's:** (a) confirm eligibility and a use case with the DigiLocker onboarding team; (b) take counsel's view on DPDP and storage of fetched documents; (c) choose which issuers matter (honours bodies, universities) and check whether they are Issuers; (d) provide an Indian server and mobile number if the operating entity is outside India.
4. Until then, the strongest status obtainable is `document` (a person uploads it, forensics run, a reviewer may confirm) or `human`.

## Risks worth naming
- Treating a DigiLocker document as `issuer` without checking *which issuer signed it* would overstate it. The adapter must record the issuer identity and the verification result, and the certificate must print only what the evidence record supports (I-8).
- Relying on a single government platform is a dependency: if the API is unavailable the flow must degrade to `document`, never to approval (I-2).
