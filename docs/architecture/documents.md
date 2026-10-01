# Documents and ingest

A workspace holds a library of sources: uploaded files, notes written in the app, and the bodies of Studio artifacts. Every source ends up the same way, as a markdown body on its `documents` row cut into passages that are embedded and indexed, so chat and search treat them alike. The API only stores bytes and enqueues a job; parsing, chunking and embedding happen in the ingest worker, one document at a time, and a document is `ready` only once it is searchable. Studio indexes an artifact's body itself, in its own worker, with the same chunking and embedding code.

**Code:** [`modules/workspaces/`](../../surfsense_local/backend/modules/workspaces/), [`modules/documents/`](../../surfsense_local/backend/modules/documents/), [`worker/ingestion/`](../../surfsense_local/backend/worker/ingestion/), [`worker/jobs.py`](../../surfsense_local/backend/worker/jobs.py), [`shared/queue.py`](../../surfsense_local/backend/shared/queue.py), [`frontend/src/features/sources/`](../../surfsense_local/frontend/src/features/sources/)
**Decisions:** [ADR 0003](../adr/0003-artifacts-as-documents.md), [ADR 0007](../adr/0007-bundled-embeddings.md), [ADR 0036](../adr/0036-the-index-records-its-embedder.md), [ADR 0008](../adr/0008-two-job-queues.md), [ADR 0009](../adr/0009-freshness-by-invalidation.md)

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
| `POST` | `/workspaces/{workspace_id}/documents` | write a note, with an optional `document_metadata` object; `201` with its body, `422` for a field it does not know |
| `POST` | `/workspaces/{workspace_id}/documents/upload` | upload files; `201` with `created`, `duplicates` and `rejected` |
| `GET` | `/workspaces/{workspace_id}/documents/{document_id}` | one document with its `content` and `document_metadata`; `content` is `null` for a `FILE` the worker has not written yet |
| `PATCH` | `/workspaces/{workspace_id}/documents/{document_id}` | rename; edit a note's content |
| `DELETE` | `/workspaces/{workspace_id}/documents/{document_id}` | delete; `409` while `processing` |
| `POST` | `/workspaces/{workspace_id}/documents/{document_id}/retry` | requeue a `failed` or `cancelled` document |
| `POST` | `/workspaces/{workspace_id}/documents/{document_id}/cancel` | stop a `pending` or `processing` ingest |
| `GET` | `/workspaces/{workspace_id}/documents/{document_id}/original` | the uploaded file, as an attachment |
| `GET` | `/workspaces/{workspace_id}/documents/by-chunk/{chunk_id}` | a cited chunk and its neighbours, for the citation panel ([`chat.md`](chat.md)) |

Chunks have no router of their own.

## Listing

- Filters are `?document_type=` and `?status=`, both repeatable. Paging is `?limit=` (default 50, at most 200) and `?offset=`. Rows come newest first, by `created_at` and then id, since one upload batch shares a second, so a fresh upload leads the sources list while it is still indexing.
- `ARTIFACT` rows are included and the caller filters them out. The sources panel asks for `document_type=FILE&document_type=NOTE`, so Studio output does not look like something the user uploaded.
- A row carries `id`, `title`, `document_type`, `status`, `error_message` and timestamps, but no `content`. The list is polled while ingest runs, and a body per row would ride along on every poll; `GET .../documents/{document_id}` returns one row with it.

## What is editable

- **Title**, always: 1 to 500 characters after trimming.
- **Content**, only for a `NOTE`. Anything else was extracted from bytes or generated, and an edit would vanish at the next ingest, so `PATCH` answers `409`. This is also the server-side read-only guard ADR 0003 asks for on artifact bodies; renaming and deleting an artifact stay allowed.
- Editing a note's content puts it back to `pending` and enqueues ingest, because until the worker rebuilds the index, search would keep returning the old text.

## Notes

A note is a document the user writes, with no file behind it. Creating one commits the row as `pending` and enqueues ingest: nothing needs parsing, but the note is not `ready` until it is chunked and indexed. A note never touches the filesystem and carries no dedup key, so two notes with the same text are two documents.

A note may carry `document_metadata`, stored as given. A plugin names itself there on the notes it adds, with `plugin_id`, `plugin_version`, `action` and `run_id`; a note the user writes has none, and editing a note leaves it alone. Writing a note with a field the API does not know is refused rather than dropped, so a client that names a field differently finds out at once.

## Upload

- The request is multipart, one `files` part per file. Each file streams to a temporary file inside the workspace directory in 1 MB reads, hashed with SHA-256 on the way past and never held whole in memory. A file over 500 MB is refused with `413`. The temporary file sits on the same filesystem as its destination, because a rename is only atomic within one filesystem.
- Only a plain extension, a dot and 1 to 16 letters or digits, is validated from the client's filename. The file is stored alone in a directory built from row ids, `data/workspaces/<workspace>/documents/<document>/`, under the client's filename made safe for every platform ([`original_file.py`](../../surfsense_local/backend/modules/documents/original_file.py)): the last path part only, with [pathvalidate](https://github.com/thombashi/pathvalidate) removing characters no filesystem accepts and suffixing Windows reserved names, leading dots dropped so the file is never hidden, cut before the extension so the whole name fits in 120 bytes, which keeps a typical Windows path under its 260-character limit, and ending in the validated extension lowercased. A name with nothing left becomes `untitled`, and one that would be `extracted.md` becomes `extracted (1).md` (see [The original file](#the-original-file)). The name reaches the disk; the path never does.
- Accepted extensions are `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, `.htm`, `.csv`, `.md`, `.markdown`, `.txt`, `.text`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp` and `.webp`. The bytes must match the extension: the PDF signature; an OOXML zip holding its main part, with at most 10,000 entries and 2 GB unpacked; UTF-8 text with no NUL and few control bytes; or an image's magic number. The MIME type stored is the server's, never the client's. The frontend mirrors the list to filter its file picker and to skip unsupported files, dropped ones included, before uploading.
- The sources panel takes files two ways: its **Add** button, and files dropped onto the panel, which shows "Drop files to add them as sources" while files are dragged over it ([`use-file-drop.ts`](../../surfsense_local/frontend/src/features/sources/use-file-drop.ts)). Both go through the same upload. The panel takes no drop while an upload runs, as **Add** is disabled then, and a drag carrying no files, such as selected text, does not light it up. A file dropped anywhere else in the window is refused ([`file-drop-guard.ts`](../../surfsense_local/frontend/src/app/file-drop-guard.ts)): unhandled, Chromium opens it in the window, and in Electron that replaces the app, since the main process lets `file:` navigation through. A dropped folder arrives as one entry with no extension and is reported as unsupported.
- `dedup_key` is the SHA-256 of the bytes and is unique per workspace. Keying on the bytes rather than the filename means the same report saved twice is one document, while two different files both called `report.pdf` are two.
- A batch is split, not rejected, except that a file over 500 MB fails the whole request with 413 and nothing in it is created. The response lists `created`, `duplicates` (each with the existing document's id) and `rejected` (each with a reason), so a dropped folder holding one known file keeps the rest.
- Accepted files become `FILE` rows in `pending`, with `mime_type`, `size_bytes` and `suffix` in `document_metadata`. The files move into place, the transaction commits, and only then is one ingest job enqueued per file, because the worker is another process and would look for rows this request had not yet written.

## Retry, cancel and delete

- **Retry** accepts a `failed` or `cancelled` document: it sets `pending`, clears `error_message` and enqueues. Without it those states would be terminal, since re-uploading the same bytes is a duplicate.
- **Cancel** accepts a `pending` or `processing` document and answers `409` otherwise. It marks the row `cancelled`, clears `error_message` and revokes any queued copy of the job (`revoke_pending`). A running job is not killed: the pipeline checks between steps and unwinds at the next one, so a long Docling parse finishes first.
- **Delete** refuses a `processing` document with `409`. Otherwise the row goes, its chunks cascade, the triggers clear both index tables, and the document's directory is removed after the commit; removing it first would leave a row describing a missing file if the transaction rolled back.
- Delete also accepts an `ARTIFACT` document, and removes the artifact's files under `artifacts/<id>/` as well as `documents/<id>/`, since a Studio output keeps its rendered blobs under the artifact's own id rather than the document's. `DELETE /artifacts/{id}` removes the same two ([`studio.md`](studio.md)).

## The original file

No filename is stored in a row: the document's directory is the record. The original is the one entry in it that is not hidden, not `Thumbs.db` or `desktop.ini`, and not `extracted.md`. Any other count, an empty or absent directory included, means the file is missing. Directories written before uploads kept their names hold `original.<ext>` beside an `extracted.md` nothing reads. They are read as they are and deliberately never rewritten: nothing in the index depends on a file's name, so renaming would only change what the file manager shows, and a bulk rename can fail part way on a file that is open or already deleted. Because `extracted.md` is never taken for the original, a legacy directory whose original was deleted reads as missing rather than serving Docling's text as the user's file.

`GET .../original` serves the stored bytes with the document's title as the filename and the stored MIME type, always as an attachment: an HTML or SVG file rendered inline would run its script against the app's origin. It answers `404` when there is no file behind the document, as for a note.

The desktop app previews an original in its left rail when its MIME type has a source viewer, starting with PDF. Other file types still open natively: through the preload bridge, Electron applies the same rule to the directory under the data directory for the given ids, since the main process never calls the backend, and hands it to the operating system, or reveals it in the file manager ([`document-files.ts`](../../surfsense_local/electron/src/main/document-files.ts)). The `DocumentRead` row carries `mime_type` from stored metadata only for `FILE`; notes always report `null`, even if their user-provided metadata contains a `mime_type`. The preview fetches the existing `/original` route, which remains an attachment so directly navigating to HTML or SVG cannot execute it on the app's origin.

## Ingest pipeline

`ingest_document(document_id)` is declared in [`modules/documents/tasks.py`](../../surfsense_local/backend/modules/documents/tasks.py), because Huey binds a task to its queue when it is decorated and the API is what enqueues it. The task body imports the pipeline lazily and Docling is imported only when the converter is first built, so the API never loads Docling or torch. Each job opens its own database engine.

1. **Start.** `begin_job` marks the row `processing` unless it was cancelled, and the worker notifies the API. The job then reads the active embedding index; with none, because onboarding has not chosen an embedder, it fails with `no embedding model has been chosen yet`.
2. **Parse** ([`parsing.py`](../../surfsense_local/backend/worker/ingestion/parsing.py)). A `NOTE` or `ARTIFACT` already has its markdown in `content`. A `FILE` with a text extension (`.md`, `.markdown`, `.txt`, `.text`) is read as UTF-8; anything else goes to Docling. OCR and table structure are switched on, so a scanned PDF is readable and a table survives as a table. RapidOCR's per-line orientation classifier is off: on noisy scans it turned upright lines 180 degrees and they read back as garbage, and dropping it cut the character error rate on generated scans about eightfold. An image is first turned upright by its EXIF orientation, which Docling ignores, and given a DPI that reads it as one A4 page, never finer than the 216 dpi OCR renders at nor coarser than its own DPI ([`image_page.py`](../../surfsense_local/backend/worker/ingestion/image_page.py)); with none, Docling takes it as 72 dpi and OCR upsampled a photo threefold. Images and PDFs share one set of options, so they share one pipeline and its models. Inference gets one thread per physical core, at most 8, as audio.cpp does, instead of Docling's 4: on an 8-core CPU that parsed generated scans, photos and PDFs 1.4 times faster. The converter is built once per process and its models load on the first conversion, so the first document a worker parses pays for the import and the load. `HF_HOME` defaults to the models directory, because Docling would otherwise write weights into `site-packages`, which is read-only in a frozen bundle. When the bundled parser pack is present Docling uses it with RapidOCR, and `HF_HUB_OFFLINE=1` is set before Docling is imported, because huggingface_hub reads it only then, so a PDF or an image converts with networking off. The markdown is kept only in `content`; nothing is written beside the original.
3. **Chunk** ([`chunking.py`](../../surfsense_local/backend/worker/ingestion/chunking.py)). Chonkie's `RecursiveChunker` splits at the coarsest boundary that fits: a heading, a paragraph, a line, a sentence, a word, then a bare split so an over-long line still ends. Passages are at most 480 tokens by bge-small's tokenizer, under its 512-token limit with room for the two tokens it adds. That tokenizer is pinned to the chunker rather than taken from the active embedder, so changing the embedder would not re-cut documents and move every chunk id. Pieces under 24 characters are merged into a neighbour while splitting, so only a document shorter than that yields a shorter passage. The tokenizer is passed as an object, because one named by a string would reach the network even offline. Each passage records the lines its first and last characters fall on.
4. **Embed** ([`encoder.py`](../../surfsense_local/backend/modules/embedding/encoder.py)). The active index's model, as its spec says, on onnxruntime's CPU provider: the document prefix, tokenize (truncated at the spec's `max_tokens`), pool, normalise, in batches of 32. For bge-small that is no prefix, 512 tokens, CLS pooling and L2 normalisation. No network and no model server. A vector whose width is not the spec's is refused rather than stored.
5. **Index** ([`indexing.py`](../../surfsense_local/backend/worker/ingestion/indexing.py)). The document's old chunks are deleted, which clears both index tables through the delete trigger, and the new chunks are inserted with their float32 embeddings, followed by one row per chunk in the active index's vector table, and the document records that index in `embedding_index_id`. The keyword index follows by trigger; the vector cannot, because only ingest holds it. Editing a note therefore stops its old text being findable.
6. **Finish.** The markdown is stored on `documents.content`, and `finish_job` writes `ready` unless a cancel won the race.

Cancellation is checked after parsing and after embedding. On any other failure the worker rolls back and re-reads the row. If the document was deleted or cancelled meanwhile it stops; otherwise it writes `failed` with `error_message` set to the exception type and message, cut to 500 characters, notifies, and re-raises so Huey runs the job again, up to two more times. A later success clears the message. The sources panel shows it and offers Retry.

**Embedding index.** Which model embeds is a property of the library, not a preference: a row in `embedding_indexes` holds the model's spec and names its vector table, which is built at the spec's width when onboarding locks the choice ([`data-model.md`](data-model.md)). `upgrade_to_head()` refuses to start when the table's width differs from the spec's. The per-batch check in `embed()` is the second line of defence. Studio indexes an artifact's body through the same index.

**Before the choice.** Onboarding gates the UI but not the API, so the routes that queue work which ends up embedded (writing, uploading, editing or retrying a document, a cloud import, and creating or regenerating a Studio artifact) answer `409` with the code `embedding_not_chosen` until an index exists.

**Models on disk.** The bge-small files (`model_optimized.onnx` and `tokenizer.json`, from `Qdrant/bge-small-en-v1.5-onnx-Q`) live in `bge-small-en-v1.5/` under the models directory. They are pinned to one revision and checked against their hashes ([`bundled.py`](../../surfsense_local/backend/modules/embedding/bundled.py)): every existing library was built with that exact file, so a different build would be a different vector space. Packaged builds ship them; a development checkout fetches them with `scripts/fetch_embedding_model.py`, which refuses a file that does not match. Any other curated embedder downloads into `embeddings/<id>/` under the data directory, since the models pack is read-only in a packaged app. Chat answers `503` while the active model's files are missing.

## The queue

- `ingest` is a `SqliteHuey` queue in `huey.db`, a file of its own so the consumer's constant polling never contends for the write lock on `surfsense.db`.
- `worker-ingest` drains it with one thread. Ingest saturates a CPU and writes to the database the API is serving from, so a second thread would spend its time behind the first one's lock. Studio has its own queue so an import never sits in front of a summary ([ADR 0008](../adr/0008-two-job-queues.md)).
- The queue survives restarts. Electron starts the workers beside the API and only the API migrates, so each consumer waits until the database is at the latest revision before taking a job ([`wait_for_schema.py`](../../surfsense_local/backend/worker/wait_for_schema.py)); a job queued before an update would otherwise run against the old schema and fail. A job carries only its task's name, so each consumer imports every task before it starts (`import_tasks()`), and [`tests/integration/test_registration.py`](../../surfsense_local/backend/tests/integration/test_registration.py) fails when that list falls behind the task modules on disk.
- Jobs are enqueued by upload, note creation, a note content edit and retry, and by import ([`import.md`](import.md)).
- A source the app quit in the middle of ingesting is failed with `interrupted when the app closed` when the ingest worker next starts, before it takes a job ([`interrupted_documents.py`](../../surfsense_local/backend/worker/interrupted_documents.py)). Huey drops a job as it starts it, so nothing else would end it, and Retry accepts only a failed or cancelled document. A source still `pending` is still queued and is left alone.
- Each transition the ingest worker makes, to `processing`, `ready` or `failed`, sends a `documents` event keyed by document id, and so does each change the API makes itself: a note written, an upload, a rename or edit, a retry, a cancel, and a delete, whose status is `deleted`. The sources panel reloads its list on each event and whenever a dropped stream is back, so a note a plugin writes shows as it is written; it still refetches every 1.5 seconds while any row is `pending` or `processing` ([`overview.md`](overview.md#freshness)).

## Known gaps

- The frontend has no way to write or edit a note, or to rename a document; the API routes exist.
- Documents have no folders (`folder_id`); import keeps the hosted folder path in `document_metadata`. This needs a design.
- Parsing runs on the CPU. Windows and Linux ship CPU-only torch and no CUDA payload ([ADR 0012](../adr/0012-vulkan-only-gpu-backend.md)).
- OCR reads one script family per converter: PP-OCRv6 covers Latin, Chinese and Japanese, so scanned Korean, Cyrillic, Devanagari or Arabic text is misread.
