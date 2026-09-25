# Desktop app overview

SurfSense is a desktop app for research over your own documents: add files, ask questions that are answered with citations into them, and turn them into deliverables such as summaries, slides, quizzes and podcasts. It serves one person on one machine and works offline: the parser, the embedding model and the model runtimes run locally, and everything the app knows lives on this machine, in one SQLite file and the files under its data directory. This page is the map of `surfsense_local/`; each feature has its own page, listed at the end.

**Code:** [`surfsense_local/backend/`](../../surfsense_local/backend/), [`surfsense_local/frontend/`](../../surfsense_local/frontend/), [`surfsense_local/electron/`](../../surfsense_local/electron/)
**Decisions:** [ADR 0004](../adr/0004-desktop-app-is-its-own-tree.md), [ADR 0005](../adr/0005-hand-written-migrations.md), [ADR 0008](../adr/0008-two-job-queues.md), [ADR 0009](../adr/0009-freshness-by-invalidation.md), [ADR 0011](../adr/0011-llama-cpp-local-runtime.md), [ADR 0016](../adr/0016-no-telemetry.md), [ADR 0017](../adr/0017-egress-off-by-default.md)

## Bird's-eye view

A file is uploaded, parsed to markdown, cut into passages and embedded. A chat turn retrieves the passages nearest the question, and a model answers from them, citing each one. A Studio job hands the selected documents' text to a model and stores the result as a document, with a file for ten of its twelve formats. Every design choice follows from who this is for:

- **One user.** There are no accounts, no auth and no users table. The API binds to `127.0.0.1` and accepts any origin, because the packaged renderer loads from `file://`.
- **Offline.** Docling parses, bge-small embeds on onnxruntime, llama-server generates text, sd-server generates images and audio.cpp's server voices podcasts, all on this machine. Remote destinations (Hugging Face for model search and downloads, and each remote host a connection points at) stay off until the user allows them ([`egress.md`](egress.md)). The app carries no telemetry or analytics code.
- **SQLite.** `surfsense.db` holds every table, the search index included: FTS5 for keywords, sqlite-vec for vectors. `huey.db` holds the job queues. Next to the hosted stack there is no Postgres or Zero, no Celery or Redis, no LangGraph and no Docker.

## Processes

```text
Electron main ─┬─ api            FastAPI on 127.0.0.1, free port    ─┐
               ├─ worker-ingest  Huey consumer, "ingest", 1 thread   ├─ surfsense.db, huey.db
               ├─ worker-studio  Huey consumer, "studio", 4 threads ─┘
               ├─ llamacpp       llama-server in router mode
               ├─ sdcpp          sd-server, started once an image model is chosen
               └─ audiocpp       audiocpp_server, started once the API names an audio model

BrowserWindow (Vite SPA) ── HTTP ──> api
api, worker-studio ── HTTP ──> llama-server, sd-server, remote OpenAI-compatible endpoints
worker-ingest, worker-studio ── POST /internal/events ──> api ── SSE /workspaces/{id}/events
```

- Electron's main process starts four sidecars at boot and supervises them ([`index.ts`](../../surfsense_local/electron/src/main/index.ts), [`sidecars/`](../../surfsense_local/electron/src/main/sidecars/)): the API, one Huey worker per queue, and llama-server. Packaged builds run frozen binaries from the app's resources; `pnpm dev` runs `uv run main.py` and `uv run worker.py <queue>`.
- llama-server starts whenever its pinned build is staged, in dev too (`pnpm build:llamacpp`, which `predev` runs). It reads per-model arguments from a preset file once at startup, so Electron restarts it when the API rewrites that file ([`local-models/runtime.md`](local-models/runtime.md)).
- sd-server takes its model as startup arguments, so it cannot start at boot. Whenever its pinned build is staged, in dev too (`pnpm build:sdcpp`, which `predev` runs), `watchImageModel` asks the API every 5 seconds which files to run, and starts, restarts or stops it on a change. The API names a model only while a Studio job needs one and for 5 minutes after, so its weights are not held beside the chat model all session ([`studio.md`](studio.md#the-image-path)).
- audiocpp_server refuses an empty model list, so it starts only once the API has written `audio/server.json` under the data directory, in dev too (`pnpm build:audiocpp`, which `predev` runs). On Windows and Linux that script compiles audio.cpp, and without a C++ toolchain the app runs without local audio ([packaging](packaging.md)). Electron checks that file every 5 seconds and restarts the server when it changes. Electron sets the machine-wide flags: the CPU backend, half the logical cores up to 8, one loaded model, and an unload after 5 idle minutes. The API writes that file whenever an audio model is installed or deleted, and at startup ([`local-models/catalog.md`](local-models/catalog.md)). The Studio worker voices podcasts there, at `SURFSENSE_LOCAL_AUDIO_BASE_URL`, and unloads the model when a podcast ends ([`studio.md`](studio.md)).
- Only the API gates the window. Electron waits up to 60 seconds for `/health` and gives up at once if the API exits. llama-server is best-effort; its state shows through `/llm/providers`.
- On macOS and Linux each child runs in its own process group. On quit Electron sends SIGTERM and, after 5 seconds, SIGKILL; on Windows it kills the process tree. A single-instance lock hands a second launch to the first window, because two sets of sidecars would fight over the SQLite file.
- The Python sidecars are configured through `SURFSENSE_LOCAL_*` variables: the API's host and port, the data and models directories, the llama-server and sd-server addresses, the images folder, audio.cpp's address and folder where it is staged, and `SURFSENSE_LOCAL_SECRET`, the key that encrypts stored API keys ([`connections.md`](connections.md)). No other sidecar receives the secret.

## Layer boundary

| Concern | Runs in |
|---|---|
| HTTP routes, OpenAPI, the chat and events streams | `api` |
| Migrations and the default workspace, at startup | `api` |
| Upload streaming, dedup and enqueueing | `api` |
| Query embedding and `retrieve()` for chat | `api`, in process |
| The chat stream and thread titles | `api` |
| Model catalog, downloads and the hardware probe | `api` |
| Parse, chunk, embed and index a document | `worker-ingest` |
| Generate and render an artifact, index its body | `worker-studio` |
| Sidecar lifecycle, the keychain secret, updates, opening files natively | Electron main |

The rules that keep the processes out of each other's way:

- The API owns the schema. `upgrade_to_head()` runs in the API's lifespan before anything else, and the workers only read and write rows ([ADR 0005](../adr/0005-hand-written-migrations.md)). The API then seeds a workspace named "My Workspace" if none exists.
- A job is enqueued after the commit that writes its row. The worker is another process and would otherwise look for a row the request had not committed.
- Workers change status through [`worker/jobs.py`](../../surfsense_local/backend/worker/jobs.py): `begin_job` marks a row `processing` unless it was cancelled, `raise_if_cancelled` runs between steps, and `finish_job` writes the terminal status only if a cancel has not won the race. A running job is never killed; it notices a cancel at its next step.
- Every connection runs in WAL mode with a 5-second busy timeout, foreign keys on and sqlite-vec loaded, and opens transactions with `BEGIN IMMEDIATE`, so a read-then-write waits for the lock instead of failing. The price is that no transaction may stay open across a slow call. The API raises if a request opens one on the event loop, and `async` handlers run each stretch of session work through `transact()` ([`api/dependencies.py`](../../surfsense_local/backend/api/dependencies.py)).
- Ingest runs one job at a time because it saturates a CPU and writes to the file the API serves from. Studio mostly waits on a model, so it runs four. Separate queues keep an import from sitting in front of a summary ([ADR 0008](../adr/0008-two-job-queues.md)).

## Freshness

- Workers call `POST /internal/events` after each status change ([`worker/notify.py`](../../surfsense_local/backend/worker/notify.py)): ingest sends a `documents` event keyed by document id, Studio an `artifacts` event keyed by artifact id. The notice is best-effort with a 2-second timeout; losing one costs a live update, never the job.
- The API fans each notice out on `GET /workspaces/{id}/events` ([`modules/events/`](../../surfsense_local/backend/modules/events/)) as a named SSE event whose data is `{"ids": [...], "status": "..."}`. The stream opens with a `: connected` comment and sends `: ping` after 15 idle seconds. The broker is an in-memory map, which holds because one uvicorn process serves the app.
- The frontend does not subscribe. The sources list and the Studio artifact list refetch every 1.5 seconds while any row is `pending` or `processing`, and stop when none is.

## Data directory

```text
~/.surfsense/                 ~/.surfsense-dev under `pnpm dev`
├── surfsense.db              every table and the search index
├── huey.db                   the ingest and studio queues
├── models/                   GGUF weights and llama-server's models.ini
├── images/                   sd-server weights (hosts with sd-server staged)
├── electron/                 Electron's userData: secret.bin, updates.json, window and theme prefs
└── data/workspaces/<id>/
    ├── documents/<id>/       original.<ext>, extracted.md
    └── artifacts/<id>/       an artifact's rendered file, named by role
```

- The bundled embedding, parser and voice models are read from `SURFSENSE_LOCAL_MODELS_DIR`: the app's resources when packaged, `backend/models` under `pnpm dev`, and `<data dir>/models` for a bare `uv run`.
- Paths under `data/` are built from row ids. The only part of a user's filename that reaches the disk is a validated extension.
- A bare `uv run` with no `SURFSENSE_LOCAL_SECRET` writes its key to `secret` beside the database.
- `SURFSENSE_LOCAL_DATA_DIR`, `SURFSENSE_LOCAL_HOST` and `SURFSENSE_LOCAL_PORT` override the defaults. Tables and files are detailed in [`data-model.md`](data-model.md).

## Frontend

- A Vite and React SPA with Tailwind and shadcn/ui primitives in `components/ui/`; assistant-ui drives the conversation. Packaged, Electron loads `frontend/dist/index.html` from disk, which is why Vite builds with relative asset paths. In dev it loads the Vite server on port 5173.
- The API's address comes from the preload: Electron passes it as a command-line argument and [`preload/index.ts`](../../surfsense_local/electron/src/preload/index.ts) exposes it as `window.surfsense.apiUrl`. In a bare browser there is no preload, requests stay root-relative, and the Vite dev server forwards `/health`, `/llm`, `/workspaces`, `/chat` and `/artifacts` to `127.0.0.1:8000`.
- The preload bridge is the renderer's only other channel: opening or revealing an original file, opening an external link, the platform name, updates, theme and the title bar. The renderer never sees Node or the sidecars.
- API calls go through `request()` in [`lib/api.ts`](../../surfsense_local/frontend/src/lib/api.ts), except the Studio viewers, which fetch an artifact's file bytes directly; an `<img>`, `<audio>` or download link takes its absolute address from `apiUrl()`. `request()` prefixes the address, turns an error body into an `ApiError` with its `code`, and when a user action is refused with `403 egress_disabled` it asks for consent and retries once.
- TanStack Query holds most server state: threads and messages, the citation panel, the model catalog and settings, an open artifact. The sources list and the Studio artifact list are component state refreshed by the poll above.
- There is no router. [`app/app-bootstrap.tsx`](../../surfsense_local/frontend/src/app/app-bootstrap.tsx) asks `GET /llm/onboarding`, then renders either onboarding ([`local-models/selection.md`](local-models/selection.md)) or the lazily loaded dashboard: the workspace rail, threads and sources on the left, the conversation in the middle, and Studio, artifacts and the citation panel on the right.
- Code is grouped by feature under `src/features/`. Each HTTP contract lives in one feature's `api.ts`, next to its hooks and components, and other features import it from there.

## Codemap

- [`backend/api/`](../../surfsense_local/backend/api/): `create_app()` and its lifespan (migrations, the default workspace, a background catalog warm-up), the per-request session and `transact()`.
- [`backend/modules/`](../../surfsense_local/backend/modules/): one folder per feature, holding whichever of its models, schemas, router and service it needs: `workspaces`, `documents`, `chunks`, `chat`, `artifacts` (Studio), `events`, `llm` (runtimes, catalog, connections, selection), `egress`, `license`, `migration` (import) and `health`. `shared.db.import_models()` imports every model at startup, because relationships name their targets as strings.
- [`backend/worker/`](../../surfsense_local/backend/worker/): `consumer.py` drains one queue per process, `jobs.py` holds status transitions and cancellation, `notify.py` the change notice, and `ingestion/` and `studio/` the two pipelines.
- [`backend/shared/`](../../surfsense_local/backend/shared/): configuration, the engine and its pragmas, `upgrade_to_head()`, the two Huey queues, `retrieve()`, and the secret that encrypts stored keys.
- [`backend/alembic/`](../../surfsense_local/backend/alembic/): revisions `0001` to `0012`, all hand-written. `env.py` has no `target_metadata`, so autogenerate cannot run by accident.
- [`frontend/src/features/`](../../surfsense_local/frontend/src/features/): `chat`, `sources`, `studio`, `workspaces`, `dashboard`, `models`, `onboarding`, `settings`, `egress`, `license`, `migration` and `updates`.
- [`electron/src/main/`](../../surfsense_local/electron/src/main/): `index.ts` (boot, window, IPC and the image-model and preset watchers), `sidecars/` (the supervisor and one spec per sidecar), `secret.ts`, `updater.ts` and `document-files.ts`.

## Where to read next

- [Data model](data-model.md): tables, the search index, revisions, files on disk.
- [Documents](documents.md): workspaces, upload, notes, the ingest pipeline.
- [Search](search.md): `retrieve()`.
- [Chat](chat.md): grounding, the stream, citations.
- [Studio](studio.md): artifact formats, jobs, viewers.
- [Connections](connections.md): OpenAI-compatible endpoints and where keys live.
- Local models: [runtime](local-models/runtime.md), [fit](local-models/fit.md), [catalog](local-models/catalog.md), [selection and onboarding](local-models/selection.md).
- [Egress](egress.md), [import](import.md), [license in the app](license/app.md), [license portal](license/portal.md), [updates](updates.md), [packaging](packaging.md), [sunset](sunset.md).
- [Contracts](../contracts/README.md) between the trees.

## Known gaps

- The frontend never subscribes to `GET /workspaces/{id}/events`; the sources and Studio lists poll every 1.5 seconds instead of invalidating on the events the workers already send.
