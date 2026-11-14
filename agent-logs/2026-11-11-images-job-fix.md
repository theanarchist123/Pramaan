# 2026-11-11 - CI images job fix

**Asked:** fix the failing GitHub Actions `images` job (`job_id=130295557416`).

## Root cause
The backend image build failed while running `playwright install --with-deps chromium` because the Playwright Node
binary could not load `libatomic.so.1`:

`.../playwright/driver/node: error while loading shared libraries: libatomic.so.1: cannot open shared object file`

## Change
- Updated `backend/Dockerfile` to install `libatomic1` before running Playwright install.

## Validation
- Built backend image with CI-equivalent arg:
  - `docker build -f backend/Dockerfile backend --build-arg WITH_EMBEDDINGS=false`
  - Succeeded locally after the fix.
- Ran secret scan on changed file (`backend/Dockerfile`): no secrets found.
- Ran CodeQL checker: no alerts found.
