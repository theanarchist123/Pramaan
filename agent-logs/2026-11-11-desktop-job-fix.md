# 2026-11-11 - CI desktop job fix

**Asked:** fix the failing GitHub Actions `desktop` job (`job_id=130297656776`).

## Root cause
`pnpm/action-setup@v4` failed because pnpm version was declared in two places:
- workflow input: `with.version: 11`
- repository `package.json`: `packageManager: pnpm@11.9.0`

The action now errors on duplicate version declarations.

## Changes
- Removed `with.version` from the desktop job's `pnpm/action-setup@v4` step in `.github/workflows/ci.yml`.
- Updated desktop pnpm build approval policy in `apps/desktop/pnpm-workspace.yaml` to allow Electron postinstall:
  - `allowBuilds.electron: true`

## Validation
- Ran desktop job commands locally after the fix:
  - `cd apps/desktop && pnpm install --no-frozen-lockfile`
  - `node scripts/test-verify.mjs`
  - Result: success (`9 checks passed`).
- Ran secret scan on changed files: no secrets found.
- Ran CodeQL checker: no alerts found.
