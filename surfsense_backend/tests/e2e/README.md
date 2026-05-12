# Backend E2E Test Harness

Strict fakes + alternative entrypoints used **only** by Playwright E2E.
Excluded from the production Docker image via `.dockerignore`.

## Files

| Path                             | Role                                                                            |
| -------------------------------- | ------------------------------------------------------------------------------- |
| `run_backend.py`                 | FastAPI entrypoint that hijacks `sys.modules` before importing `app.app:app`    |
| `run_celery.py`                  | Celery worker entrypoint with the same hijack + patch logic                     |
| `middleware/scenario.py`         | `X-E2E-Scenario` header → ContextVar (read by fakes)                            |
| `fakes/composio_module.py`       | Strict drop-in for the `composio` package; raises on unknown surface            |
| `fakes/llm.py`                   | `fake_get_user_long_context_llm` returning a `FakeListChatModel`                |
| `fakes/embeddings.py`            | Deterministic 0.1-vector `embed_text` / `embed_texts`                           |
| `fakes/fixtures/drive_files.json`| Canned Drive listings + file contents (incl. canary tokens)                     |

## Why a sys.modules hijack?

Production code does `from composio import Composio` at module load
time. By the time the FastAPI app object exists, that binding has
already been resolved. The hijack runs **before** any `app.*` import,
so the binding resolves to our strict fake. No production source
changes; fakes are physically excluded from production images.

Belt + suspenders + no internet: the strict `__getattr__` in every
fake raises `NotImplementedError` if a future production code path
introduces a new SDK call. CI also sets `HTTPS_PROXY=http://127.0.0.1:1`
plus sentinel API keys so any leaked outbound HTTP fails immediately.

## Adding a new fake

1. Create `fakes/<sdk>_module.py` modelled on `composio_module.py`.
2. In `run_backend.py` and `run_celery.py`, register
   `sys.modules["<sdk>"] = _fake_<sdk>` before the `from app.app import app`
   line.
3. If the new fake needs scenario branching, read from
   `tests.e2e.middleware.scenario.current_scenario()`.

## Reused by backend integration tests

The strict fakes are not only for Playwright. Backend route integration
tests can import the same fake before importing `app.app`, so Composio
route tests exercise production route code without touching the real
SDK:

```python
from tests.e2e.fakes import composio_module as _fake_composio
sys.modules["composio"] = _fake_composio
from app.app import app
```

See `surfsense_backend/tests/integration/composio/conftest.py` for the
current pattern.

## Running locally

```bash
cd surfsense_backend
uv run python tests/e2e/run_backend.py
# in a second shell:
uv run python tests/e2e/run_celery.py
```

Then in `surfsense_web`:

```bash
pnpm test:e2e
```
