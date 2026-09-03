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

The API runs on its own; the Electron shell, SPA, and worker land in later phases.

```bash
cd backend
uv sync
uv run main.py                # http://127.0.0.1:8000
uv run pytest
```

Interactive docs at `/docs`, schema at `/openapi.json`. Host and port come from
`SURFSENSE_LOCAL_HOST` and `SURFSENSE_LOCAL_PORT`.

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
| `web/` | Vite + React SPA |
| `electron/` | Main process, sidecar lifecycle |
| `backend/api/` | FastAPI routes, migrations |
| `backend/worker/` | Huey consumer, ingest and Studio pipelines |
| `backend/shared/` | Models, search, paths used by both |
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
