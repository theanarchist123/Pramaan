# Pramaan — *Don't claim it. Prove it.*

An AI-native **Who's Who of India**. People are interviewed by an AI (voice or text, in their language), every claim
is fact-checked against evidence, and what survives is sealed into a **cryptographically signed certificate** that
anyone can verify — without trusting us.

Most registries ask you to *say* who you are. Pramaan makes the registry itself the proof: each claim is badged
**self-declared / web-evidenced / document-verified**, the certificate carries an Ed25519 signature, and every
issuance is appended to a public, hash-chained transparency log.

|                       |                                                                                                  |
| --------------------- | ------------------------------------------------------------------------------------------------ |
| **Web app**     | Next.js 15 · Tailwind 4 · shadcn/ui · English + हिन्दी · installable PWA · light/dark |
| **Desktop app** | Electron shell with tray, global shortcut `Ctrl+Shift+P`, `pramaan://` deep links            |
| **Public API**  | FastAPI, OpenAPI at `/docs`, API keys with scopes + rate limits, signed webhooks               |
| **Build on it** | Python + TypeScript SDKs, MCP server for other AI agents, embeddable badge, Telegram bot example |
| **Agents**      | 10 named agents orchestrated with LangGraph, watchable live in *Mission Control*               |

## Architecture

```mermaid
flowchart LR
  subgraph Clients
    W[Web app / PWA]
    D[Desktop app]
    T[Telegram bot]
    M[MCP clients<br/>other AI agents]
    X[Your app<br/>via SDK + API key]
  end
  W & D & T & M & X --> API[FastAPI /v1<br/>auth · API keys · rate limits]

  API --> ORCH{{LangGraph orchestrator<br/>events → SSE}}
  ORCH --> A1[Saathi<br/>interviewer]
  ORCH --> A2[Khoji-Pehle<br/>"is this you?" discovery]
  ORCH --> A3[Pariksha<br/>fact-checker]
  ORCH --> A4[Lipik<br/>document reader]
  ORCH --> A5[Prahari<br/>auditor]
  ORCH --> A6[Setu<br/>graph builder · plain code]
  ORCH --> A7[Khoji<br/>semantic search]
  ORCH --> A8[Doot<br/>outreach]
  ORCH --> A9[Shilpkar<br/>builder]
  ORCH --> A10[Chitrakar<br/>deterministic art · plain code]

  A1 & A2 & A3 & A4 & A5 & A7 --> LLM[(LLM layer<br/>Gemini fallback chain<br/>· offline mock)]
  A9 --> GUARD[AST code guard] --> SBX[Docker sandbox<br/>no network · read-only] --> HUMAN{{Human approves}} --> PLUG[Hot-loaded plugin]

  API --> DB[(Postgres + pgvector<br/>profiles · claims · edges · embeddings)]
  A10 --> SIGN[Ed25519 signing<br/>+ hash-chained log] --> DB
  API --> WH[Signed webhooks]
```

### How trust works

1. **Claims, not facts.** Every statement is a claim with a status and confidence. Self-declared claims stay labelled as such.
2. **Evidence.** Pariksha looks for public evidence; a *verbatim-quote check* rejects hallucinated citations. Web evidence is capped at 0.9, a matching identity document at 0.97.
3. **Auditor gate.** Prahari (fixed rules; a model only checks the bio) auto-approves only at ≥ 0.95 *with* a matching document from a recognised issuer. Every owner's first listing, every award claim, common names without a second identifying detail, and any edit to an approved profile go to a human. The fail-safe is to escalate. Public evidence comes from Wikipedia and Wikidata (crowd-edited, not official registries); DigiLocker/PAN/Aadhaar checks are not implemented.
4. **Seal.** The verified claims are canonicalised → SHA-256 → **Ed25519** signature. The public key is published at `/.well-known/pramaan-keys.json`.
5. **Transparency.** Each issuance is appended to a public hash chain (`/transparency`); tampering with history breaks every later link.
6. **Verify anywhere.** The QR on the certificate opens `/verify/<code>`. The *Try to tamper* page edits a field and shows exactly which one breaks the signature.

### Shilpkar — features written by AI, safely

Ask for a capability ("add a patents field", "an endpoint for city statistics"). Shilpkar writes a plugin, then:
**AST allow-list guard** (read-only, no reflection) → **Docker sandbox** (`--network none --read-only --cap-drop ALL`, 512 MB, 128 pids, non-root) → bounded **self-repair loop** (2 attempts) → **human approval** → hot-load under `/v1/plugins/<slug>`. No code runs in the API without a person saying yes.

## Quick start

Requirements: Docker. (For local development: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22+, pnpm.)

### One command

```bash
cp .env.example .env          # add GEMINI_API_KEY, or leave LLM_MODE=mock to run fully offline
docker compose up --build
```

Web [http://localhost:3000](http://localhost:3000) · API docs [http://localhost:8000/docs](http://localhost:8000/docs)

`LLM_MODE=mock` is a deterministic offline mode: the whole product, every agent included, works with no API key — handy for demos on bad Wi-Fi.

### Local development

```bash
docker compose up -d db                                   # Postgres + pgvector

# API
cd backend
uv venv --python 3.12 && uv pip install -e ".[dev]"
.venv/Scripts/python scripts/seed_demo.py                 # 37 clearly-fictional demo profiles + demo admin
.venv/Scripts/python -m uvicorn app.main:app --port 8000  # (Linux/macOS: .venv/bin/python)

# Web
cd apps/web
pnpm install && pnpm build && pnpm start --port 3100      # or: pnpm dev
```

Demo admin (review queue, dashboard): `admin@pramaan.demo` / `pramaan-demo-1` — **change before any real deployment**.

### Desktop app

```bash
cd apps/desktop
pnpm install
node node_modules/electron/install.js    # pnpm 11 skips install scripts
pnpm start                               # dev;  PRAMAAN_URL=https://your-server to point elsewhere
pnpm package                             # electron-builder → dist/ installer for the OS you run it on (Windows NSIS, macOS dmg, Linux AppImage/deb)
pnpm test                                # offline-verifier vectors (signed by the Python backend) + 11 security/behaviour checks against the real app
```

Releases, signing and auto-update: push a tag `desktop-vX.Y.Z` and `.github/workflows/desktop-release.yml` builds Windows, macOS and Linux installers on their own runners, signs them when the certificate secrets are set (`WIN_CSC_LINK`/`WIN_CSC_KEY_PASSWORD`, `CSC_LINK`/`CSC_KEY_PASSWORD` + `APPLE_ID`/`APPLE_APP_SPECIFIC_PASSWORD`/`APPLE_TEAM_ID`), and publishes them to the GitHub Release. The installed app checks that release every 6 hours (`electron-updater` verifies the signed manifest), downloads quietly and installs when the user next quits. Unsigned builds work but trigger SmartScreen/Gatekeeper warnings; get certificates before shipping. To point an installed app at your server without rebuilding, put `{"url": "https://your-server"}` in `config.json` inside the app's user-data folder (survives updates).

**Offline verification:** *Pramaan → Verify a certificate file (offline)…* (Ctrl+O) checks a certificate's `.json` (the verify page's *JSON (offline check)* button) with no network: it re-hashes the payload and checks the Ed25519 signature against registry keys the app cached earlier (only cached keys are trusted, never one inside the file). It cannot see revocations; open the certificate online for that. Set `apiUrl` in the desktop `config.json` if your API is not on localhost:8000.

Hardened by default: context isolation + sandbox, no Node in the page, window locked to the app's origin, every permission denied, single instance, and `pramaan://verify/<code>` · `profile/<slug>` · `onboard` · `directory` deep links that are strictly validated.

## Build on Pramaan

|                |                                                                                                                                                                |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| REST API       | `http://localhost:8000/docs` — create a key under *Developers* in the web app                                                                             |
| Python SDK     | `packages/sdk/python` — `pip install -e packages/sdk/python`                                                                                              |
| TypeScript SDK | `packages/sdk/typescript` — typed from the OpenAPI schema                                                                                                   |
| Webhooks       | HMAC-signed (`X-Pramaan-Signature: t=…,v1=…`), retried, delivery log, SSRF-checked                                                                         |
| Badge          | `/v1/badge/profile/<slug>.svg` and `/v1/badge/certificate/<code>.svg` — embed anywhere                                                                    |
| MCP server     | `mcp/server.py` — gives Claude/other agents `search_registry`, `get_profile`, `verify_certificate`, `check_document_content`, `registry_overview` |
| Example app    | `examples/telegram-bot` — built **only** on the public API + SDK                                                                                      |

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest      # API, agents, signing, sandbox guard, webhooks … (LLM mocked)
cd apps/web && node scripts/smoke.mjs             # Playwright smoke tests (also smoke-directory/-developers/-builder)
cd apps/desktop && pnpm test
python scripts/ai_stats.py                        # how much of this repo was written by AI (needs git history)
```

## Project layout

```text
apps/web         Next.js app (UI, i18n, PWA)          packages/sdk   Python + TypeScript SDKs
apps/desktop     Electron shell                       mcp            MCP server
backend          FastAPI, agents, signing, services   examples       third-party apps built on the API
sandbox          Dockerfile for Shilpkar's test runs  scripts        repo-level tooling (AI authorship ledger)
```

## Honest notes

- **Demo data is fictional** and labelled *Demo*. Pre-fill uses public sources only, is marked *suggested, unverified*, and never issues a certificate for a person who hasn't consented.
- Wikipedia lookups need `WIKIMEDIA_CONTACT` (an email or URL — Wikimedia's bot policy). Without it, lookups are refused and profiles simply go to human review.
- `PLUGINS_ENABLED` and `WEBHOOK_ALLOW_PRIVATE` default to `false` (the Docker image forces them off). They exist for local development only.
- Authenticated personal data follows the spirit of India's DPDP Act: explicit consent ledger, export-my-data, delete-my-data.
