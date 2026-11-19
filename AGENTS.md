# AGENTS.md - standing instructions for coding agents

The full plan is `PRAMAAN_V2_OVERHAUL_SPEC.md`. Work one phase at a time; stop at each phase gate and report.

## Invariants (never break; each needs an automated test that fails if violated)

- **I-1** The LLM never makes the final approval decision; deterministic rules do.
- **I-2** Any error escalates to a human. Never approve or publish on failure.
- **I-3** Untrusted text is data: wrap and escape it before any model call.
- **I-4** AI-written code runs only after guard -> sandbox -> tests -> policy approval.
- **I-5** No certificate without consent and verified claims.
- **I-6** Signing keys never reach a UI or a log.
- **I-7** Model-drafted outreach cannot contain links or addresses the model added.
- **I-8** A certificate labels a claim only with a status backed by an evidence record of that kind
  (`services/certificates.py::backed_claims`).
- **I-9** The UI says "verified" only from the server enum (`status` + `decision_basis`); never "independently" unless
  every printed claim is `document` or `issuer`.
- **I-10** Nobody approves, overrides or reviews their own profile.

## Workflow

- One PR per task ID (`TRU-00`, `PG-03`...). Tests first. Do not weaken or delete an existing test to get green; if a
  test is wrong, fix it and say why in the commit body.
- Never squash or rewrite history. Every AI-authored commit carries `Co-Authored-By: <the model>`.
- Always-human-review paths: `core/signing.py`, `core/keys.py`, `agents/prahari.py`, `services/code_guard.py`,
  `services/sandbox.py`, `migrations/`, auth/RBAC code, `docs/security/`.
- Run before calling a task done: backend `pytest`; web `pnpm lint && pnpm build`; desktop `pnpm test`.
  Integration tests need Postgres: `docker compose up -d db`.
- Append a session entry to `agent-logs/` at the end of every session.
- If the spec conflicts with the code you find, stop, write the conflict to `agent-logs/`, and ask the human.
- Anything the spec marks **(verify)** about the outside world (laws, vendor APIs, browser support, licences) must be
  checked against the official source and recorded in `docs/adr/` before it is relied on.

## Design rules (Phase 1 onwards)

- Use tokens from `packages/ui` only; no hard-coded colours. Sentence case; no tracked all-caps labels; no emoji in
  status lines.
- Animations come from the v3 motion catalogue (`docs/design/v3/motion.md`, V-01..V-15; supersedes M-01..M-28, approved by the owner
  2026-11-13) with a reduced-motion variant; transform/opacity only; motion reflects real events. Visual direction: `docs/design/v3/`
  (marigold + ink, Bricolage Grotesque, floating transparent navigation; supersedes Seal & Ink).
- Unsplash API images are hotlinked with attribution and never self-hosted. Certificates use only frozen local images.
  Never use stock photos of people.
- Status is always icon + text + colour. Screens are English only for now (`docs/adr/0016-english-only-screens.md`); any Hindi screen copy must be written natively and reviewed before `HINDI_UI_ENABLED` is turned on.

## Commands

```
backend:  cd backend && .venv/Scripts/python -m pytest -q
evals:    cd backend && .venv/Scripts/python -m evals.run [--live]
web:      cd apps/web && pnpm lint && pnpm build
desktop:  cd apps/desktop && pnpm test
audit:    python backend/scripts/audit_certificates.py [--revoke]
```
