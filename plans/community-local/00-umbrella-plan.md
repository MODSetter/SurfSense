# SurfSense Community Local — Umbrella Plan

> Airgapped, local-first NotebookLM-style desktop app (Community SKU).

**Three workstreams** — pick a folder and work through phases in order:

| Workstream | Folder | Owns |
|---|---|---|
| **Frontend** | [`frontend/`](frontend/) | `surfsense_local/frontend/` |
| **API** | [`api/`](api/) | `electron/`, `backend/api/`, migrations, packaging |
| **Worker** | [`worker/`](worker/) | `backend/worker/`, ingest, `shared/search`, studio pipelines |

Shared: [`00c-data-model.md`](00c-data-model.md), [`00b-diagrams.md`](00b-diagrams.md).

> **SCOPE:** New tree **`surfsense_local/`** — not a feature flag on Docker SurfSense.

## Phase index

Same phase number = integrate together.

| Phase | [`frontend/`](frontend/) | [`api/`](api/) | [`worker/`](worker/) |
|---|---|---|---|
| **0** | — | [`00-spike.md`](api/00-spike.md) | echo in [`01-boot.md`](worker/01-boot.md) |
| **1** | [`01-shell.md`](frontend/01-shell.md) ◐ | [`01-skeleton.md`](api/01-skeleton.md) ◐ | [`01-boot.md`](worker/01-boot.md) |
| **2** | [`02-documents.md`](frontend/02-documents.md) | [`02-upload.md`](api/02-upload.md) | [`02-ingest.md`](worker/02-ingest.md) |
| **3** | [`03-chat.md`](frontend/03-chat.md) | [`03-chat.md`](api/03-chat.md) | [`03-search.md`](worker/03-search.md) |
| **4** | [`04-studio.md`](frontend/04-studio.md) | [`04-studio.md`](api/04-studio.md) | [`04-studio.md`](worker/04-studio.md) |
| **5** | [`05-install-ux.md`](frontend/05-install-ux.md) | [`05-packaging.md`](api/05-packaging.md) | [`05-packaging.md`](worker/05-packaging.md) |

**Demo:** phase 3 all streams. **Ship:** phase 5.

◐ started · ✓ done · unmarked not begun. Built: a Vite + shadcn shell reading
`/health`, and on the API side the migrations, workspace CRUD and document CRUD.
Phase 1 still owes both those screens, the Electron dev script, and the worker.

## Layer boundary

| Concern | API | Worker |
|---|---|---|
| HTTP / OpenAPI | ✓ | |
| Upload stream + enqueue | ✓ | |
| Docling / chunk / embed | | ✓ |
| Hybrid search | calls | implements (`shared/`) |
| Chat LLM stream | ✓ | |
| Studio builder | | ✓ |
| Electron / installers | ✓ | |

## Positioning

| | Connected / Docker | Community Local |
|---|---|---|
| DB | Postgres + Zero | SQLite |
| Jobs | Celery + Redis | Huey `-w 1` |
| Chat | LangGraph | Retrieve-first RAG |
| Auth | Yes | None |
| UI | Next + Zero | Vite in Electron |

## Out of scope

Docker Compose, Postgres, Zero, Redis, Celery, LangGraph, git KB, scrapers, MCP, multi-seat LAN, Stripe.

## Locked decisions

| Decision | Choice | Why |
|---|---|---|
| **HTTP stack** | **FastAPI** + uvicorn | Same stack as cloud backend; native OpenAPI for frontend; SSE streaming for chat. PyInstaller risk is handled in [`api/00-spike.md`](api/00-spike.md) — not a reason to downgrade. |
| **Retrieval** | **FTS5 + sqlite-vec hybrid (RRF)** | Semantic + keyword from day one. Embeddings on ingest must be queried properly — not keyword-only, not in-memory scan over BLOBs. |
| **Embed provider** | Same Ollama / llama.cpp endpoint as chat | One local model server; embedding model name in `app_settings`. |
| **Persistence** | SQLAlchemy 2.0 + Alembic, same as cloud | Models are the source of truth. `versions/` ships as PyInstaller data, resolved from the package's own `__file__` — de-risked in [`api/00-spike.md`](api/00-spike.md). |
| **Migrations** | **Hand-written; autogenerate is off** | Autogenerate cannot see a rename — it emits drop + add, which deletes a column's data silently. The target database is one user's laptop, unbacked and uninspectable, so every revision is written and read by a person. `env.py` carries no `target_metadata`, so `--autogenerate` cannot be used by accident. Same call Open WebUI makes across all 58 of its SQLite revisions. |
| **Schema owner** | Alembic only; **never** `create_all` | Cloud's `create_all`-on-startup races its own migrations and breaks releases. Local has one path to a schema, and a test fails if models and migrations drift. |
| **Model layout** | One slice per feature: `modules/<slice>/models.py` | Vertical slices, as in cloud's `automations/`, `notifications/`. `shared.db.import_models()` registers all of them at app creation: relationships name their target as a string, so a slice nobody imported is a name SQLAlchemy cannot resolve, and every query against a table pointing at it fails at runtime. |
| **Test layout** | `tests/unit/<slice>` and `tests/integration/<slice>`, marked per module | Mirrors cloud, down to `pytestmark = pytest.mark.integration` at the top of each file. Nothing is mocked: integration means a real SQLite file in `tmp_path` built by the migrations, which is what caught the unresolved relationship above. |

## Open items

First Studio artifact type (summary vs podcast); model pack hosting (Phase 5 only); default workspace on first launch.

## Copy sources

`surfsense_backend/app/routes/documents_routes.py`, `app/services/docling_service.py`, `etl_pipeline/`, `surfsense_web/`.
