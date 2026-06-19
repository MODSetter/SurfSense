# Tests

How the backend test suite is organized and the conventions to follow when adding tests.

## Layout: type-first, module-mirrored

Tests are split by **type** at the top level, and each type **mirrors the `app/` module tree** inside:

```
tests/
├── conftest.py                  # global fixtures + DATABASE_URL pinning
├── unit/                        # pure logic: no DB, no app, no network
│   └── notifications/
│       ├── api/test_transform.py
│       └── service/
│           ├── messages/test_connector_indexing.py
│           └── test_metadata.py
└── integration/                 # real PostgreSQL (pgvector)
    ├── conftest.py              # async engine, transactional db_session, db_user, ...
    └── notifications/
        ├── conftest.py          # module-scoped fixtures (e.g. transactional client)
        └── test_*_handler.py
```

To find a feature's tests, look under `tests/<type>/<same path as app/>`.

## Unit vs integration

- `@pytest.mark.unit` — pure, fast, no I/O. Test behavior through a public function's inputs/outputs.
- `@pytest.mark.integration` — requires a real database. Run with `AUTH_TYPE=LOCAL`.

Maximize logic covered by unit tests; keep integration tests for what genuinely needs the DB (persistence, SQL filters, scoping, HTTP wiring).

## Principles

- **Behavior, not implementation.** Assert observable outputs (returned values, persisted rows, HTTP responses), never private helpers. Tests should survive a refactor.
- **Functional core / imperative shell.** Put pure decision logic in a side-effect-free module (e.g. `app/notifications/service/messages/`) so it is unit-testable; keep the persistence shell thin and cover it with a few integration tests.
- **One responsibility per test file**, mirroring the slice it covers.
- **Mock only at system boundaries** (external APIs, brokers), never internal collaborators. Prefer dependency overrides and the transactional `db_session` over mocks.

## Fixtures

`conftest.py` is scoped to its directory and below. Keep truly global fixtures in `tests/conftest.py`; put module-specific fixtures in that module's `conftest.py` so a DB fixture never loads for a pure unit test.

For API integration tests, override `get_async_session` and `get_auth_context` to ride the test's transactional `db_session` (see `tests/integration/notifications/conftest.py`): rows seeded in the test and rows read via the endpoint share one transaction that rolls back automatically.

## Import mode

The suite uses `--import-mode=importlib` with `pythonpath = ["."]` (see `pyproject.toml`). This lets test files share basenames across modules (e.g. many `test_api.py`) without `__init__.py` boilerplate; new test directories do not need an `__init__.py`.

## Running

```bash
# fast unit tests
uv run pytest -m unit

# integration (needs Postgres + pgvector)
AUTH_TYPE=LOCAL uv run pytest -m integration

# a single module's tests
uv run pytest tests/unit/notifications
```
