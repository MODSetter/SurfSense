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
| **1** | [`01-shell.md`](frontend/01-shell.md) ◐ | [`01-skeleton.md`](api/01-skeleton.md) ✓ | [`01-boot.md`](worker/01-boot.md) ✓ |
| **2** | [`02-documents.md`](frontend/02-documents.md) | [`02-upload.md`](api/02-upload.md) ✓ | [`02-ingest.md`](worker/02-ingest.md) ✓ |
| **3** | [`03-chat.md`](frontend/03-chat.md) | [`03-chat.md`](api/03-chat.md) ✓ | [`03-search.md`](worker/03-search.md) ✓ |
| **4** | [`04-studio.md`](frontend/04-studio.md) | [`04-studio.md`](api/04-studio.md) | [`04-studio.md`](worker/04-studio.md) |
| **5** | [`05-install-ux.md`](frontend/05-install-ux.md) | [`05-packaging.md`](api/05-packaging.md) | [`05-packaging.md`](worker/05-packaging.md) |

**Demo:** phase 3 all streams. **Ship:** phase 5.

◐ started · ✓ done · unmarked not begun. Built: a Vite + shadcn shell reading
`/health`, the whole API surface for workspaces and documents — migrations,
CRUD, upload, retry, and the search index with the triggers that keep it in step
— and a worker that ingests what the API enqueues: Docling parses, Chonkie
chunks, bundled bge-small embeds, both index tables written, `ready` or `failed`
with a reason. The generation slice ([`modules/llm/`](../../surfsense_local/backend/modules/llm/))
also lands ahead of its phase: list and pull Ollama models, a curated Qwen
catalog, and a selectable model per role — everything
[`api/03-chat.md`](api/03-chat.md) needs except the stream itself. Retrieval
lands too ([`shared/search.py`](../../surfsense_local/backend/shared/search.py)):
`retrieve()` scopes to a workspace, widens recall with a BM25 leg and a vector KNN
leg, then rescores the union by cosine. **Chat now closes on all of it**
([`modules/chat/`](../../surfsense_local/backend/modules/chat/)): a thread's turn
retrieves its own context, grounds a system prompt with citable `<source>` blocks,
slides a window over history, and streams a cited reply over SSE while both turns
persist. The Electron shell and dev loop now land too: [`electron/`](../../surfsense_local/electron/)
spawns both Python sidecars, waits on `/health`, and loads the Vite SPA, reaping
the sidecars on quit (guarded by `pnpm check:sidecars`). Phase 1 still owes both
screens, and a PDF only converts on a machine that can reach
Hugging Face until [`api/05-packaging.md`](api/05-packaging.md) ships the parser
pack.

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
| **Retrieval** | **FTS5 + sqlite-vec hybrid, cosine rescore** | Semantic + keyword from day one: both legs widen recall, cosine orders. Embeddings on ingest must be queried properly — not keyword-only, not in-memory scan over BLOBs. |
| **Embed provider** | Bundled bge-small-en-v1.5 int8, in-process on onnxruntime | 384-dim, ~66MB, runs offline on CPU with no model server. Docling parses, Chonkie chunks. Remote embedding is a later opt-in, not a launch dependency. |
| **Generation provider** | Ollama default; curated Qwen catalog; provider `Protocol`s | `modules/llm/`. A `Generator` answers, a `ModelStore` downloads; a remote API satisfies only the first, so the download UI is gated by `isinstance`, not a provider name. Ollama has no library API, so the offered models are a curated Qwen list inside the Ollama provider. `SelectedModel(role)` holds the choice. Adding a provider is a folder plus one registry line. |
| **Persistence** | SQLAlchemy 2.0 + Alembic, same as cloud | Models are the source of truth. `versions/` ships as PyInstaller data, resolved from the package's own `__file__` — de-risked in [`api/00-spike.md`](api/00-spike.md). |
| **Migrations** | **Hand-written; autogenerate is off** | Autogenerate cannot see a rename — it emits drop + add, which deletes a column's data silently. The target database is one user's laptop, unbacked and uninspectable, so every revision is written and read by a person. `env.py` carries no `target_metadata`, so `--autogenerate` cannot be used by accident. Mature SQLite-backed apps make the same call — hand-written revisions throughout. |
| **Schema owner** | Alembic only; **never** `create_all` | Cloud's `create_all`-on-startup races its own migrations and breaks releases. Local has one path to a schema, and a test fails if models and migrations drift. |
| **Model layout** | One folder per feature: `modules/<feature>/models.py` | As in cloud's `automations/`, `notifications/`. `shared.db.import_models()` registers all of them at app creation: relationships name their target as a string, so a feature nobody imported is a name SQLAlchemy cannot resolve, and every query against a table pointing at it fails at runtime. |
| **Test layout** | `tests/unit/<feature>` and `tests/integration/<feature>`, marked per module | Mirrors cloud, down to `pytestmark = pytest.mark.integration` at the top of each file. Nothing is mocked: integration means a real SQLite file in `tmp_path` built by the migrations, which is what caught the unresolved relationship above. |
| **UI freshness** | **TanStack Query on the client; SSE `/events` invalidation; no sync engine** | Zero gave cloud two things — cross-client sync and reactive queries. Local is one user, one SQLite file: nothing to sync between clients, so that half is deleted. The reactive half stays. The worker flips a row (`pending → ready`) in a *separate* process, so it POSTs a tiny `/internal/events` to the API, which fans out a named SSE event carrying only IDs; the client calls `queryClient.invalidateQueries`. Polling (`refetchInterval`) is the trivial fallback. No WebSockets, no local replica. Endpoints (`/events`, `/internal/events`) are a queued API slice; the client adopting TanStack Query is the frontend's. |

## Open items

First Studio artifact type (summary vs podcast); model pack hosting (Phase 5 only); default workspace on first launch. **Queued API slice:** the freshness push — `GET /workspaces/{id}/events` (SSE fan-out to the renderer) and `POST /internal/events` (worker → API notify on row change); consumed by the frontend via `queryClient.invalidateQueries` (see the UI freshness decision).

## Copy sources

`surfsense_backend/app/routes/documents_routes.py`, `app/services/docling_service.py`, `etl_pipeline/`, `surfsense_web/`.
