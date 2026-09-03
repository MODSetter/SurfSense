# API — Phase 2: Upload

> Schema: [`../00c-data-model.md`](../00c-data-model.md).
> Copy source: `surfsense_backend/app/routes/documents_routes.py` (stream + 2-phase, not Celery).

## Goal

Accept files, persist metadata, enqueue ingest.

## Work

- `POST /workspaces/{id}/documents/upload` — multipart, **stream to disk**.
- Path: `~/.surfsense/data/workspaces/{id}/documents/{id}/original.{ext}`.
- Insert `documents`: `status=pending`, `dedup_key`, metadata.
- `ingest_document.delay(document_id)` — one Huey job per file.
- Return document ids immediately; add route + pydantic models (auto in `/openapi.json`).

## Acceptance

- Upload returns fast; row `pending`; file on disk.
- Re-upload same file → dedup or clear error per workspace.

## Interface to worker

`ingest_document(document_id)` — [`../worker/02-ingest.md`](../worker/02-ingest.md).
