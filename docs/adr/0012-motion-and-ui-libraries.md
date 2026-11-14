# ADR 0012: Motion and UI libraries for the v3 redesign

Status: accepted (2026-11-13, owner approved the Phase 0 gate). GSAP, Aceternity and Three.js remain not used.

## Licences and versions (read from the vendors' own files or npm metadata on 2026-11-13)

| Library | Version | Licence | Source checked | Decision |
|---|---|---|---|---|
| motion | 14.14.0 (repo has ^14.10.1) | MIT | npm metadata | use (already installed) |
| @number-flow/react | 0.6.2 | MIT | npm metadata (repo `LICENSE` path returned 404 on `main`) | use |
| canvas-confetti | 1.9.4 | ISC | npm metadata | use, lazy-loaded |
| rough-notation | 0.5.1 | MIT | npm metadata | use sparingly |
| @formkit/auto-animate | 0.10.2 | MIT | npm metadata | use in staff Desk lists |
| @rive-app/react-canvas | 4.39.0 | MIT | `rive-app/rive-react` `LICENSE` file | use, lazy-loaded |
| lenis | 1.3.27 | MIT | `darkroomengineering/lenis` `LICENSE` file | optional, marketing pages only |
| @fontsource-variable/bricolage-grotesque | 5.3.0 | OFL-1.1 | npm metadata | use (headline font) |
| Magic UI (copy-in components) | n/a | MIT | GitHub licence record for `magicuidesign/magicui` | use |
| React Bits (copy-in components) | n/a | MIT + Commons Clause | `DavidHDev/react-bits` `LICENSE.md` | allowed inside Pramaan; components must never be sold, sublicensed or redistributed on their own |
| GSAP 3.15.1 | | "Standard no charge" licence, not OSI | npm metadata only; licence text at gsap.com/standard-license NOT read | **not used** until the text is read |
| Aceternity UI | | free-tier licence not confirmed from its own pages | search snippets only | **not used** |
| Three.js / React Three Fiber | | | | not used: weight on mid-range Android phones |
| CRED NeoPOP (Apache-2.0, last push Oct 2023) | | | | inspiration only, not a dependency |

## Not yet verified (do not rely on)
- Rive editor pricing and the licence of any community `.riv` assets. The mascot needs a character we own or have a licence for.
- Next.js 15.5 View Transitions support (experimental flag) and browser support for the View Transitions API.

## Rules
- Copy-in components are reviewed like our own code (they enter `apps/web/src/components/`), keep their licence header, and are listed in `docs/design/v3/motion.md`.
- No dependency is added until this ADR is accepted.
