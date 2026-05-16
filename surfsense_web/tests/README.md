# Playwright E2E Suite

End-to-end tests for the full SurfSense stack (Next.js + FastAPI +
Celery + Postgres + Redis). Designed to scale from one connector
(Composio Drive in Phase 1) to every connector + manual file upload
without rewriting the harness.

## How the deterministic harness works

There are **three layers of defense** against accidental real-world
calls. None of them touch production code.

1. `surfsense_backend/tests/e2e/run_backend.py` and `run_celery.py` are
   separate entrypoints (not used by `python main.py`). They hijack
   `sys.modules["composio"]` BEFORE importing the app, swap in strict
   fakes for `langchain_litellm`/`langchain_openai`, and mount the
   `X-E2E-Scenario` middleware.
2. The fakes themselves are **strict**: every class implements
   `__getattr__` that raises `NotImplementedError` on unknown surface.
   Adding a new SDK call site without updating the fake fails CI loudly.
3. CI sets `HTTPS_PROXY=http://127.0.0.1:1` plus sentinel API keys
   (`COMPOSIO_API_KEY=e2e-deny-real-call-sentinel`). Any leaked outbound
   HTTP call fails before reaching the network.

## Running locally

The recommended flow runs only Postgres and Redis in Docker, and the backend
+ Celery worker on the host. The E2E entrypoints `setdefault` every backend
variable they need, so no `.env` file is required on a fresh checkout.

### One-time setup

From `surfsense_web/`:

```bash
pnpm install
pnpm exec playwright install --with-deps chromium
```

### Each run

**1. Bring up Postgres + Redis** from the repo root:

```bash
docker compose -f docker/docker-compose.deps-only.yml up -d db redis
```

**2. Start the backend** in `surfsense_backend/`, terminal A:

```bash
uv sync
uv run alembic upgrade head
uv run python tests/e2e/run_backend.py
```

**3. Start the Celery worker** in `surfsense_backend/`, terminal B:

```bash
uv run python tests/e2e/run_celery.py
```

**4. Register the Playwright user**:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e-test@surfsense.net","password":"E2eTestPassword123!"}'
```

**5. Run Playwright** from `surfsense_web/`, terminal C:

```bash
pnpm test:e2e             # dev server (fast iteration)
pnpm test:e2e:headed      # show the browser
pnpm test:e2e:ui          # Playwright UI mode
pnpm test:e2e:debug       # Playwright Inspector
pnpm test:e2e:prod        # build + start (matches CI exactly)
pnpm test:e2e:report      # open the last HTML report
```

`playwright.config.ts` and the backend run scripts share defaults, so the
above works without exporting any env vars. Override
`PLAYWRIGHT_TEST_EMAIL`, `PLAYWRIGHT_TEST_PASSWORD`, or
`NEXT_PUBLIC_FASTAPI_BACKEND_URL` only when pointing tests at a different
stack.

To debug a single journey:

```bash
pnpm test:e2e:headed connectors/composio/drive/journey.spec.ts
```

### Hermetic alternative (matches CI)

To reproduce the CI environment exactly: backend and Celery in containers
with L3 egress denied, replace steps 1–3 with:

```bash
docker compose -f docker/docker-compose.e2e.yml up -d --build --wait
```

Then run steps 4 (curl register) and 5 (`pnpm test:e2e:prod`) as above. Tear
down with:

```bash
docker compose -f docker/docker-compose.e2e.yml down -v --remove-orphans
```

This builds the ~9 GB e2e backend image, so the deps-only flow is faster for
day-to-day work.

## Adding a new connector

The directory tree is designed so a new connector lives mostly inside
its own folder. E2E is scoped to **one user expectation per connector**:
the smallest browser journey that proves the user-visible outcome works.
Follow this checklist:

1. **Backend fake.** Add a new file under
   `surfsense_backend/tests/e2e/fakes/<sdk>_module.py` mirroring
   `composio_module.py`. Use `__getattr__` to raise on unknown surface.
2. **Hijack.** Wire the new module into `run_backend.py` and
   `run_celery.py` with `sys.modules["<sdk>"] = <fake>`.
3. **Backend tests.** Put edge cases in backend tests, not Playwright:
   OAuth state validation in unit tests, and route/error branches in
   `surfsense_backend/tests/integration/<connector>/`.
4. **Fixtures.** Drop a fixture file into `tests/fixtures/connectors/`
   that returns a pre-connected connector row.
5. **Journey spec.** Create exactly one
   `tests/connectors/<vendor>/<service>/journey.spec.ts` for the user
   expectation. For indexable connectors this usually means
   connect -> select scope -> index -> assert canary content. For
   connection-only connectors this means connect -> assert connected badge.
6. **Update this README's directory diagram.**

Do not add separate Playwright specs for expired OAuth state, duplicate
connectors, auth-expired classification, or route config persistence.
Those belong in backend unit/integration tests such as
`surfsense_backend/tests/unit/utils/test_oauth_security.py` and
`surfsense_backend/tests/integration/composio/`.

## Why API-driven?

Journey specs prefer a thin browser assertion followed by API-driven
configuration/indexing because:

- It keeps tests **deterministic** (no waiting on UI animation,
  React hydration, or Next.js compile time).
- It exercises the **same backend code path** the UI eventually calls.
- The expensive E2E assertion stays focused on what only E2E can prove:
  the cross-process seam from connector -> Celery -> indexing -> DB.

UI-only tests live under `helpers/ui/` for future Phase 2 work
(folder-tree drag-and-drop, indexing options switches, etc.).
