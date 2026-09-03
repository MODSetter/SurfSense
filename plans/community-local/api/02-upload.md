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
- `POST /workspaces/{id}/documents/{doc}/retry` — requeue a `failed` document.
  Without it `failed` is terminal: re-uploading the same bytes hits
  `(workspace_id, dedup_key)` and is rejected, so an ingest that died because the
  model server was down could never be recovered.
- `GET /workspaces/{id}/documents/{doc}/original` — serve the stored file.
- **Extend both deletes** (`DELETE /workspaces/{id}` and
  `DELETE .../documents/{doc}`, both shipped in phase 1) to remove the document
  directory and the rows in `chunks_fts` and `chunk_vectors`. Those are virtual
  tables with no foreign keys, so the database cascade does not reach them and a
  delete would leave the index answering for documents that no longer exist.

## Acceptance

- Upload returns fast; row `pending`; file on disk.
- Re-upload same file → dedup or clear error per workspace.
- Retry moves a `failed` document back to `pending` and clears `error_message`.
- Deleting a document leaves no file on disk and no row in the search index.

## Interface to worker

`ingest_document(document_id)` — [`../worker/02-ingest.md`](../worker/02-ingest.md).
