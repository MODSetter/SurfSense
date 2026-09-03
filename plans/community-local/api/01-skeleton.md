# API — Phase 1: Skeleton

> Owns: `electron/`, `backend/api/`, `backend/shared/` migrations.
> Schema: [`../00c-data-model.md`](../00c-data-model.md).

## Goal

Dev loop + workspace CRUD. FastAPI serves live OpenAPI for frontend.

## Work

- Repo layout: `electron/`, `backend/api/`, `backend/worker/` (stub OK).
- **FastAPI** app + uvicorn; pydantic request/response models on every route.
- OpenAPI auto at **`/openapi.json`**; Swagger UI at **`/docs`** — no hand-maintained spec file.
- SQLite migrations: `workspaces`, stub `documents`.
- Routes: `POST/GET /workspaces`, `GET /workspaces/{id}/documents` (empty list OK).
- Electron dev script: Vite + `uvicorn` + worker together.
- Data dir: `~/.surfsense/surfsense.db`, `huey.db`.

## Acceptance

- Create workspace via API; persists restart.
- Frontend can build against `/openapi.json` (or `/docs`) while API runs.

## Interface to worker

None yet — worker runs idle consumer ([`../worker/01-boot.md`](../worker/01-boot.md)).
