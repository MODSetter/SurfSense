# SurfSense Community Local

Local-first desktop app for research over your own documents. Runs fully offline with your own models — no Docker, no account, no data leaving the machine.

## Features

- **Workspaces** — group documents per project
- **Ingest** — PDFs and files parsed with Docling, chunked and embedded locally
- **Chat with citations** — hybrid retrieval (BM25 + vector) grounded in your documents
- **Studio** — generate artifacts (summaries, podcasts) from selected documents
- **Airgapped** — models and parsers on disk; nothing calls home

## Requirements

| | |
|---|---|
| Node.js | 18+ |
| Python | 3.12+ |
| Local LLM | [Ollama](https://ollama.com) or `llama.cpp` on `127.0.0.1` |

## Development

API and worker run as two processes, one terminal each. The Electron shell that
starts them together lands in a later phase.

```bash
cd backend
uv sync
uv run scripts/fetch_embedding_model.py  # one-time local retrieval model
uv run main.py                # API on http://127.0.0.1:8000
uv run worker.py              # consumer; uploads stay pending without it
uv run pytest
```

Interactive docs at `/docs`, schema at `/openapi.json`. `SURFSENSE_LOCAL_HOST`,
`SURFSENSE_LOCAL_PORT`, and `SURFSENSE_LOCAL_DATA_DIR` override the defaults.

Migrations run on startup and are written by hand — `--autogenerate` is switched
off deliberately, because it renders a rename as a drop plus an add and the
database it runs against is the user's only copy. After changing a model, write
the revision yourself; a test fails if models and migration history disagree:

```bash
uv run alembic revision -m "add x to y"
```

Anything touching a table that already holds rows should read the live schema
first (`op.get_bind()`, `sa.inspect`) rather than assuming its shape.

## Architecture

Electron spawns two Python sidecars. The UI only talks HTTP to the API; heavy work is queued to a single serial worker.

```text
Electron ─┬─> FastAPI (127.0.0.1)  ──> surfsense.db
          └─> Huey worker (-w 1)   ──> surfsense.db, huey.db
                                   └─> Docling, embeddings
Vite SPA  ───> FastAPI                 Ollama / llama.cpp
```

| Path | Contents |
|---|---|
| `frontend/` | Vite + React SPA, shadcn/ui |
| `electron/` | Main process, sidecar lifecycle |
| `backend/api/` | App factory, session dependency |
| `backend/modules/` | One folder per feature: models, schemas, routes |
| `backend/worker/` | Huey consumer, ingest and Studio pipelines |
| `backend/shared/` | Engine, session, Alembic entrypoint |
| `backend/alembic/` | Migration history; the only thing that creates schema |
| `packaging/` | PyInstaller + electron-builder specs |

## Data directory

All runtime state lives outside the repo:

```text
~/.surfsense/
├── surfsense.db              # workspaces, documents, chunks, chats
├── huey.db                   # job queue
├── models/                   # LLM + parser packs
└── data/workspaces/<id>/     # originals, extracted text, artifacts
```

## License

Apache 2.0 — see [LICENSE](../LICENSE).
