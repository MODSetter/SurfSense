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
  - **`chunk_vectors`** — insert the `vec0` row with `rowid = chunks.id`
  - store `embedding` BLOB on `chunks` for export/reindex
  - `status=ready` | `failed` + message
- Parser pack: bundled or first-run download (not HF at runtime).

**Already done, in [`../api/02-upload.md`](../api/02-upload.md):** both index
tables and their triggers exist, and `shared/db.py` loads the sqlite-vec
extension on every connection, worker included. `chunks_fts` needs no writing —
a trigger mirrors `chunks.content` on insert, update and delete. `chunk_vectors`
still needs its row written here, since only ingest holds the embedding, but the
delete side is a trigger too.

**Dimension `D`** is `SURFSENSE_LOCAL_EMBEDDING_DIMENSION`, default 768 for
nomic-embed-text. `upgrade_to_head` refuses to open a database whose
`chunk_vectors` was created at another width, so a changed model is caught at
startup rather than by silently mixing unrelated vectors.

## Acceptance

- Single PDF offline → `ready`; chunk retrievable via both FTS5 and vec0 smoke queries.
- Five PDFs → serial processing.
- Kill mid-job → retry or `failed`.

## Interface from API

Triggered after upload — [`../api/02-upload.md`](../api/02-upload.md).
