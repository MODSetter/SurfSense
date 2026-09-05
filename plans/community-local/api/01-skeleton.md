# API — Phase 1: Skeleton

> Owns: `electron/`, `backend/api/`, `backend/shared/` migrations.
> Schema: [`../00c-data-model.md`](../00c-data-model.md).

## Goal

Dev loop + workspace CRUD. FastAPI serves live OpenAPI for frontend.

## Work

- Repo layout: `electron/`, `backend/api/`, `backend/worker/` (stub OK).
- **FastAPI** app + uvicorn; pydantic request/response models on every route.
- OpenAPI auto at **`/openapi.json`**; Swagger UI at **`/docs`** — no hand-maintained spec file.
- SQLite migrations: every table Local ships with, in one hand-written revision.
- Workspaces: `GET/POST /workspaces`, `GET/PATCH/DELETE /workspaces/{id}`.
- Documents, everything that needs no file on disk: `GET/POST
  /workspaces/{id}/documents`, `GET/PATCH/DELETE /workspaces/{id}/documents/{doc}`.
  `POST` writes a `NOTE`; upload is [phase 2](02-upload.md).
- List filters and paging per [`../00c-data-model.md`](../00c-data-model.md).
- Electron dev script: Vite + `uvicorn` + worker together. ✓ `electron/` shell —
  `pnpm dev` runs the frontend and Electron; Electron spawns both sidecars (so
  quitting reaps them), waits on `/health`, then loads the SPA. `check:sidecars`
  guards the lifecycle. Preload hands the API base URL to the renderer as
  `window.surfsense.apiUrl`.
- Data dir: `~/.surfsense/surfsense.db`, `huey.db`.

## Acceptance

- Create workspace via API; persists restart.
- Deleting a workspace takes its documents and their chunks with it.
- A note's body is editable and returns the document to `pending`; a `FILE`
  body is not.
- Frontend can build against `/openapi.json` (or `/docs`) while API runs.

## Interface to worker

None yet — worker runs idle consumer ([`../worker/01-boot.md`](../worker/01-boot.md)).
