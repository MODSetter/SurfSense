# Documents and ingest

A workspace holds a library of sources: uploaded files, notes written in the app, and the bodies of Studio artifacts. Every source ends up the same way, as a markdown body on its `documents` row cut into passages that are embedded and indexed, so chat and search treat them alike. The API only stores bytes and enqueues a job; parsing, chunking and embedding happen in the ingest worker, one document at a time, and a document is `ready` only once it is searchable. Studio indexes an artifact's body itself, in its own worker, with the same chunking and embedding code.

**Code:** [`modules/workspaces/`](../../surfsense_local/backend/modules/workspaces/), [`modules/documents/`](../../surfsense_local/backend/modules/documents/), [`worker/ingestion/`](../../surfsense_local/backend/worker/ingestion/), [`worker/jobs.py`](../../surfsense_local/backend/worker/jobs.py), [`shared/queue.py`](../../surfsense_local/backend/shared/queue.py), [`frontend/src/features/sources/`](../../surfsense_local/frontend/src/features/sources/)
**Decisions:** [ADR 0003](../adr/0003-artifacts-as-documents.md), [ADR 0007](../adr/0007-bundled-embeddings.md), [ADR 0008](../adr/0008-two-job-queues.md), [ADR 0009](../adr/0009-freshness-by-invalidation.md)

## Workspaces

| Method | Path | Does |
|---|---|---|
| `POST` | `/workspaces` | create; `201` |
| `GET` | `/workspaces` | list, oldest first |
| `GET` | `/workspaces/{workspace_id}` | read one |
| `PATCH` | `/workspaces/{workspace_id}` | rename |
| `DELETE` | `/workspaces/{workspace_id}` | delete it and everything in it; `204` |

- The API seeds "My Workspace" at startup when no workspace exists ([`seed.py`](../../surfsense_local/backend/modules/workspaces/seed.py)), so a first launch always has one to open into.
- A name is trimmed and must be 1 to 200 characters, so a name of spaces fails instead of rendering blank.
- Delete cascades the workspace's documents (with their chunks and index entries), threads, messages and artifacts, then removes `data/workspaces/<id>/` after the commit, which a rollback would undo.
- Every route with a workspace in its path resolves it first and answers `404` for an unknown id. A document is looked up within the workspace in its path, so one workspace's id cannot reach another's document.

## Document routes

| Method | Path | Does |
|---|---|---|
| `GET` | `/workspaces/{workspace_id}/documents` | list (below) |
| `POST` | `/workspaces/{workspace_id}/documents` | write a note; `201` with its body |
| `POST` | `/workspaces/{workspace_id}/documents/upload` | upload files; `201` with `created`, `duplicates` and `rejected` |
| `PATCH` | `/workspaces/{workspace_id}/documents/{document_id}` | rename; edit a note's content |
| `DELETE` | `/workspaces/{workspace_id}/documents/{document_id}` | delete; `409` while `processing` |
| `POST` | `/workspaces/{workspace_id}/documents/{document_id}/retry` | requeue a `failed` or `cancelled` document |
| `POST` | `/workspaces/{workspace_id}/documents/{document_id}/cancel` | stop a `pending` or `processing` ingest |
| `GET` | `/workspaces/{workspace_id}/documents/{document_id}/original` | the uploaded file, as an attachment |
| `GET` | `/workspaces/{workspace_id}/documents/by-chunk/{chunk_id}` | a cited chunk and its neighbours, for the citation panel ([`chat.md`](chat.md)) |

Chunks have no router of their own.

## Listing

- Filters are `?document_type=` and `?status=`, both repeatable. Paging is `?limit=` (default 50, at most 200) and `?offset=`. Rows come oldest first.
- `ARTIFACT` rows are included and the caller filters them out. The sources panel asks for `document_type=FILE&document_type=NOTE`, so Studio output does not look like something the user uploaded.
- A row carries `id`, `title`, `document_type`, `status`, `error_message` and timestamps, but no `content`. The list is polled while ingest runs, and a body per row would ride along on every poll.

## What is editable

- **Title**, always: 1 to 500 characters after trimming.
- **Content**, only for a `NOTE`. Anything else was extracted from bytes or generated, and an edit would vanish at the next ingest, so `PATCH` answers `409`. This is also the server-side read-only guard ADR 0003 asks for on artifact bodies; renaming and deleting an artifact stay allowed.
- Editing a note's content puts it back to `pending` and enqueues ingest, because until the worker rebuilds the index, search would keep returning the old text.

## Notes

A note is a document the user writes, with no file behind it. Creating one commits the row as `pending` and enqueues ingest: nothing needs parsing, but the note is not `ready` until it is chunked and indexed. A note never touches the filesystem and carries no dedup key, so two notes with the same text are two documents.

## Upload

- The request is multipart, one `files` part per file. Each file streams to a temporary file inside the workspace directory in 1 MB reads, hashed with SHA-256 on the way past and never held whole in memory. A file over 500 MB is refused with `413`. The temporary file sits on the same filesystem as its destination, because a rename is only atomic within one filesystem.
- Only a plain extension, a dot and 1 to 16 letters or digits, is taken from the client's filename. The stored path is built from row ids, `data/workspaces/<workspace>/documents/<document>/original.<ext>`, so nothing else a user types reaches the filesystem.
- Accepted extensions are `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, `.htm`, `.csv`, `.md`, `.markdown`, `.txt`, `.text`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp` and `.webp`. The bytes must match the extension: the PDF signature; an OOXML zip holding its main part, with at most 10,000 entries and 2 GB unpacked; UTF-8 text with no NUL and few control bytes; or an image's magic number. The MIME type stored is the server's, never the client's. The frontend mirrors the list to filter its file picker and to skip unsupported files, dragged-in ones included, before uploading.
- `dedup_key` is the SHA-256 of the bytes and is unique per workspace. Keying on the bytes rather than the filename means the same report saved twice is one document, while two different files both called `report.pdf` are two.
- A batch is split, not rejected, except that a file over 500 MB fails the whole request with 413 and nothing in it is created. The response lists `created`, `duplicates` (each with the existing document's id) and `rejected` (each with a reason), so a dropped folder holding one known file keeps the rest.
- Accepted files become `FILE` rows in `pending`, with `mime_type`, `size_bytes` and `suffix` in `document_metadata`. The files move into place, the transaction commits, and only then is one ingest job enqueued per file, because the worker is another process and would look for rows this request had not yet written.

## Retry, cancel and delete

- **Retry** accepts a `failed` or `cancelled` document: it sets `pending`, clears `error_message` and enqueues. Without it those states would be terminal, since re-uploading the same bytes is a duplicate.
- **Cancel** accepts a `pending` or `processing` document and answers `409` otherwise. It marks the row `cancelled`, clears `error_message` and revokes any queued copy of the job (`revoke_pending`). A running job is not killed: the pipeline checks between steps and unwinds at the next one, so a long Docling parse finishes first.
- **Delete** refuses a `processing` document with `409`. Otherwise the row goes, its chunks cascade, the triggers clear both index tables, and the document's directory is removed after the commit; removing it first would leave a row describing a missing file if the transaction rolled back.
- Delete also accepts an `ARTIFACT` document, but it removes only `documents/<id>/`, so the artifact's files under `artifacts/<id>/` stay on disk. `DELETE /artifacts/{id}` removes both ([`studio.md`](studio.md)).

## The original file

`GET .../original` serves the stored bytes with the document's title as the filename and the stored MIME type, always as an attachment: an HTML or SVG file rendered inline would run its script against the app's origin. It answers `404` when there is no file behind the document, as for a note.

The desktop app opens originals natively instead. Through the preload bridge, Electron finds the single `original.<ext>` under the data directory for the given ids and hands it to the operating system, or reveals it in the file manager ([`document-files.ts`](../../surfsense_local/electron/src/main/document-files.ts)).

## Ingest pipeline

`ingest_document(document_id)` is declared in [`modules/documents/tasks.py`](../../surfsense_local/backend/modules/documents/tasks.py), because Huey binds a task to its queue when it is decorated and the API is what enqueues it. The task body imports the pipeline lazily and Docling is imported only when the converter is first built, so the API never loads Docling or torch. Each job opens its own database engine.

1. **Start.** `begin_job` marks the row `processing` unless it was cancelled, and the worker notifies the API.
2. **Parse** ([`parsing.py`](../../surfsense_local/backend/worker/ingestion/parsing.py)). A `NOTE` or `ARTIFACT` already has its markdown in `content`. A `FILE` with a text extension (`.md`, `.markdown`, `.txt`, `.text`) is read as UTF-8; anything else goes to Docling. OCR and table structure are switched on, so a scanned PDF is readable and a table survives as a table. The converter is built once per process, because its constructor loads the layout models. `HF_HOME` defaults to the models directory, because Docling would otherwise write weights into `site-packages`, which is read-only in a frozen bundle. When the bundled parser pack is present Docling uses it with RapidOCR and `HF_HUB_OFFLINE=1`, so a PDF converts with networking off. The markdown is also written beside the original as `extracted.md`.
3. **Chunk** ([`chunking.py`](../../surfsense_local/backend/worker/ingestion/chunking.py)). Chonkie's `RecursiveChunker` splits at the coarsest boundary that fits: a heading, a paragraph, a line, a sentence, a word, then a bare split so an over-long line still ends. Passages are at most 480 tokens by bge-small's own tokenizer, under its 512-token limit with room for the two tokens it adds. Pieces under 24 characters are merged into a neighbour while splitting, so only a document shorter than that yields a shorter passage. The tokenizer is passed as an object, because one named by a string would reach the network even offline. Each passage records the lines its first and last characters fall on.
4. **Embed** ([`embedding.py`](../../surfsense_local/backend/worker/ingestion/embedding.py)). bge-small-en-v1.5 as an int8 ONNX model on onnxruntime's CPU provider: tokenize (truncated at 512), CLS-pool, L2-normalise, in batches of 32. No network and no model server. A vector whose width is not the configured dimension is refused rather than stored.
5. **Index** ([`indexing.py`](../../surfsense_local/backend/worker/ingestion/indexing.py)). The document's old chunks are deleted, which clears both index tables through the delete trigger, and the new chunks are inserted with their float32 embeddings, followed by one `chunk_vectors` row per chunk. The keyword index follows by trigger; the vector cannot, because only ingest holds it. Editing a note therefore stops its old text being findable.
6. **Finish.** The markdown is stored on `documents.content`, and `finish_job` writes `ready` unless a cancel won the race.

Cancellation is checked after parsing and after embedding. On any other failure the worker rolls back and re-reads the row. If the document was deleted or cancelled meanwhile it stops; otherwise it writes `failed` with `error_message` set to the exception type and message, cut to 500 characters, notifies, and re-raises so Huey runs the job again, up to two more times. A later success clears the message. The sources panel shows it and offers Retry.

**Embedding dimension.** `SURFSENSE_LOCAL_EMBEDDING_DIMENSION` (default 384) is schema, not preference: `chunk_vectors` is created at that width, and `upgrade_to_head()` refuses to start against a database built at another one ([`data-model.md`](data-model.md)). The per-batch check in `embed()` is the second line of defence.

**Models on disk.** The bge-small files (`model_optimized.onnx`, `tokenizer.json` and `config.json`, from `Qdrant/bge-small-en-v1.5-onnx-Q`) live in `bge-small-en-v1.5/` under the models directory. Packaged builds ship them; a development checkout fetches them with `scripts/fetch_embedding_model.py`. Chat answers `503` while they are missing.

## The queue

- `ingest` is a `SqliteHuey` queue in `huey.db`, a file of its own so the consumer's constant polling never contends for the write lock on `surfsense.db`.
- `worker-ingest` drains it with one thread. Ingest saturates a CPU and writes to the database the API is serving from, so a second thread would spend its time behind the first one's lock. Studio has its own queue so an import never sits in front of a summary ([ADR 0008](../adr/0008-two-job-queues.md)).
- The queue survives restarts. A job carries only its task's name, so each consumer imports every task before it starts (`import_tasks()`), and [`tests/integration/test_registration.py`](../../surfsense_local/backend/tests/integration/test_registration.py) fails when that list falls behind the task modules on disk.
- Jobs are enqueued by upload, note creation, a note content edit and retry, and by import ([`import.md`](import.md)).
- Each transition the ingest worker makes, to `processing`, `ready` or `failed`, sends a `documents` event keyed by document id; the API's own changes, to `pending` and `cancelled`, send none. The frontend does not listen yet; the sources panel refetches every 1.5 seconds while any row is `pending` or `processing` ([`overview.md`](overview.md#freshness)).

## Known gaps

- There is no `GET /workspaces/{id}/documents/{doc}`. The list omits `content` by design, and `DocumentDetail`, the row plus its `content`, is returned only when a note is created, so no route returns the body of a file or a note.
- The frontend has no way to write or edit a note, or to rename a document; the API routes exist.
- Deleting an `ARTIFACT` document through `DELETE /workspaces/{id}/documents/{doc}` removes its rows but leaves its files under `artifacts/<id>/`; only `DELETE /artifacts/{id}` removes them.
- Documents have no folders (`folder_id`); import keeps the hosted folder path in `document_metadata`. This needs a design.
