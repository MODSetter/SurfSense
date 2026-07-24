# Backend E2E Harness

This directory contains the test-only backend entrypoints and fakes used by
Playwright. They are not part of the production image: `.dockerignore` excludes
`tests/`, and the E2E Docker stage copies this directory through a separate
build context.

## Files

| Path | Purpose |
| --- | --- |
| `run_backend.py` | Starts FastAPI after installing the test fakes into `sys.modules`. |
| `run_celery.py` | Starts the Celery worker with the same fake setup. |
| `middleware/scenario.py` | Reads `X-E2E-Scenario` into a request-scoped context var. |
| `fakes/composio_module.py` | Fake `composio` package used by connector flows. |
| `fakes/llm.py` | Fake chat model factory. |
| `fakes/embeddings.py` | Deterministic embedding helpers. |
| `fakes/fixtures/drive_files.json` | Drive fixture data and canary file contents. |

## Why the import hook exists

Some production modules import SDK clients at module load time, for example
`from composio import Composio`. By the time `app.app` has been imported, those
bindings are already fixed.

The E2E entrypoints install fake modules in `sys.modules` before importing any
`app.*` module. That lets the normal production code run while SDK calls resolve
to local fakes.

The fakes should fail loudly. If production starts using a new SDK method that
the fake does not implement, add that method to the fake instead of letting the
test call the real service.

## Adding a fake

1. Add `fakes/<sdk>_module.py`.
2. Register it in both `run_backend.py` and `run_celery.py` before importing
   `app.app` or `app.celery_app`.
3. If the fake needs per-test behavior, read the current scenario from
   `tests.e2e.middleware.scenario.current_scenario()`.

## Shared with backend integration tests

Backend integration tests can use the same fakes when they need production route
code without the real SDK:

```python
from tests.e2e.fakes import composio_module as _fake_composio
sys.modules["composio"] = _fake_composio
from app.app import app
```

See `surfsense_backend/tests/integration/composio/conftest.py` for the current
pattern.

## Running locally

The recommended local flow runs only Postgres and Redis in Docker, and the
backend + Celery worker on the host. No `.env` file is required: both
entrypoints `setdefault` every variable they need (DB URL, Redis URL,
sentinel API keys, etc.) to values that match `docker-compose.deps-only.yml`.

### One-time setup

From `surfsense_web/`:

```bash
pnpm install
pnpm exec playwright install --with-deps chromium
```

### Each run

**1. Bring up Postgres + Redis** from the repo root (the other deps-only
services (Zero, pgAdmin) are not needed for E2E):

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
pnpm test:e2e:prod        # build + start (matches CI exactly)
```

`playwright.config.ts` and the run scripts share defaults, so this works on a
fresh checkout. Set `PLAYWRIGHT_TEST_EMAIL`, `PLAYWRIGHT_TEST_PASSWORD`,
`NEXT_PUBLIC_FASTAPI_BACKEND_URL`, or any backend env (e.g. `DATABASE_URL`)
only when pointing tests at a different stack.

### Cleanup

```bash
docker compose -f docker/docker-compose.deps-only.yml down
```

Add `-v` to also wipe the Postgres volume.

### Hermetic alternative (matches CI)

To reproduce the CI environment exactly — backend and Celery in containers,
network egress denied at L3 — replace steps 1–3 with:

```bash
docker compose -f docker/docker-compose.e2e.yml up -d --build --wait
```

Then run steps 4 (curl register) and 5 (`pnpm test:e2e:prod`) as above. Tear
down with:

```bash
docker compose -f docker/docker-compose.e2e.yml down -v --remove-orphans
```

This builds the ~9 GB `surfsense-e2e-backend:local` image, so the deps-only
flow above is faster for day-to-day development.
