# Worker — Phase 2: Ingest

> Copy: `surfsense_backend/app/services/docling_service.py`, `etl_pipeline/`.
> Schema: [`../00c-data-model.md`](../00c-data-model.md) (`chunks`, FTS5, sqlite-vec).

## Goal

`ingest_document` → Docling → chunks → embeddings → indexed → `ready` | `failed`.

## Work

- `@task(retries=2) ingest_document(document_id)`:
  - `status=processing`
  - Docling → markdown → `content` + `extracted.md` on disk
  - chunk → insert `chunks` row
  - embed each chunk via Ollama/llama.cpp (**same provider as search**)
  - **`chunks_fts`** — FTS5 row sync on insert/update
  - **`chunk_vectors`** — sqlite-vec `vec0` row; rowid = `chunks.id`; dimension `D` from settings
  - store `embedding` BLOB on `chunks` for export/reindex
  - `status=ready` | `failed` + message
- Load sqlite-vec extension at worker startup (`sqlite_vec.load(db)`).
- Parser pack: bundled or first-run download (not HF at runtime).

## Acceptance

- Single PDF offline → `ready`; chunk retrievable via both FTS5 and vec0 smoke queries.
- Five PDFs → serial processing.
- Kill mid-job → retry or `failed`.
- Wrong embedding dimension → clear error, no silent corrupt index.

## Interface from API

Triggered after upload — [`../api/02-upload.md`](../api/02-upload.md).
