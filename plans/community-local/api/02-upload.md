# API — Phase 2: Upload

> Schema: [`../00c-data-model.md`](../00c-data-model.md).
> Copy source: `surfsense_backend/app/routes/documents_routes.py` (stream + 2-phase, not Celery).

## Goal

Accept files, persist metadata, enqueue ingest.

## Work — done

- `POST /workspaces/{id}/documents/upload` — multipart, streamed to disk in 1 MB
  reads and hashed on the way past. Never held whole: a 400 MB PDF read into
  memory is what makes cloud's upload route expensive.
- Path: `~/.surfsense/data/workspaces/{id}/documents/{id}/original.{ext}`. Built
  from row ids, and only a plain extension is taken from the client's filename,
  so nothing a user types reaches the filesystem.
- Insert `documents`: `status=pending`, `dedup_key`, metadata.
- One Huey job per file, enqueued **after** the commit. The worker is another
  process and would otherwise go looking for a row this request had not written.
- A batch is split, not rejected: the response carries `created` and
  `duplicates`, so a dropped folder holding one known file keeps the rest.
- `POST /workspaces/{id}/documents/{doc}/retry` — requeue a `failed` document.
  Without it `failed` is terminal: re-uploading the same bytes hits
  `(workspace_id, dedup_key)` and is rejected, so an ingest that died because the
  model server was down could never be recovered.
- `GET /workspaces/{id}/documents/{doc}/original` — served as an attachment
  always, since a stored html or svg rendered inline would run its own script
  against the app's origin.
- Both deletes remove the document directory, after the commit rather than
  before: a rollback would otherwise leave a row describing a file that is gone.

**`dedup_key` is a hash of the bytes**, not of the filename as in cloud. Keying
on the name means the same report saved twice ingests twice, while two genuinely
different files called `report.pdf` collide and the second is refused.

**The search index cleans itself.** `chunks_fts` and `chunk_vectors` are virtual
tables no foreign key reaches, but triggers on `chunks` carry inserts, updates
and deletes across — and they fire on cascade, which is how every real delete
arrives, since the user removes a document or a workspace and never a chunk.

## Acceptance

- Upload returns fast; row `pending`; file on disk.
- Re-upload same bytes → reported as a duplicate, per workspace.
- Retry moves a `failed` document back to `pending` and clears `error_message`.
- Deleting a document leaves no file on disk and no row in the search index.

## Interface to worker

`ingest_document(document_id)` — declared in `modules/documents/tasks.py`, since
Huey binds a task to its queue at decoration and the API is what enqueues it.
Body in [`../worker/02-ingest.md`](../worker/02-ingest.md).
