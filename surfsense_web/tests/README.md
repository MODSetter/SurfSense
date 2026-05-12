# Playwright E2E Suite

End-to-end tests for the full SurfSense stack (Next.js + FastAPI +
Celery + Postgres + Redis). Designed to scale from one connector
(Composio Drive in Phase 1) to every connector + manual file upload
without rewriting the harness.

## Layout

```
tests/
├── auth.setup.ts                    # one-time login, persists localStorage
├── smoke/                           # tracer-bullet tests (dashboard renders)
├── connectors/
│   └── composio/
│       └── drive/                   # Composio Google Drive — Phase 1
│           └── journey.spec.ts      # connect -> select -> index -> canary assertion
├── fixtures/                        # test.extend() fixtures
│   ├── index.ts                     # named `test` exports per spec category
│   ├── search-space.fixture.ts      # apiToken + per-test search space
│   └── connectors/
│       └── composio-drive.fixture.ts
├── helpers/                         # reusable building blocks
│   ├── api/                         # backend HTTP helpers
│   ├── ui/                          # page-object selectors
│   ├── waits/                       # deterministic polling
│   └── canary.ts                    # canary tokens + fixed Drive file ids
└── README.md                        # this file
```

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

```bash
# 1. Bring up Postgres + Redis (Docker compose, supabase, whatever you use)
docker compose up -d postgres redis

# 2. Backend with E2E entrypoint (note: NOT `uv run main.py`)
cd surfsense_backend
uv run alembic upgrade head
uv run python tests/e2e/run_backend.py &

# 3. Celery worker with the same entrypoint pattern
uv run python tests/e2e/run_celery.py &

# 4. Run Playwright tests (auto-starts `pnpm dev` via webServer config)
cd ../surfsense_web
pnpm test:e2e
```

For CI behavior in one go: `pnpm test:e2e:headless`.

To debug the Drive journey: `pnpm test:e2e -- connectors/composio/drive/journey.spec.ts --headed`.

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
