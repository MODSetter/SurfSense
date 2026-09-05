# Worker — Phase 2: Ingest

> Owns: `worker/ingestion/`. Schema: [`../00c-data-model.md`](../00c-data-model.md).

## Goal

`ingest_document` -> markdown -> chunks -> embeddings -> indexed -> `ready` | `failed`.

## Work — done

One folder, one job per file, all under `worker/ingestion/`:

- **`pipeline.py`** takes one document from `pending` to `ready`: parse, chunk,
  embed, write the rows, store the markdown on `documents.content`. A failure
  rolls back, writes `status=failed` with `error_message`, and re-raises so
  Huey retries; a run that succeeds clears the message, and the retry route
  already exists for the case that does not.
- **`parsing.py`** reads `.md`, `.txt` and extensionless files straight off
  disk and sends everything else to Docling, whose converter is built once per
  process behind an `lru_cache` because its constructor loads the layout
  models. OCR and table structure are named on, not left to the default, so a
  scanned PDF is readable and a table survives as a table. Docling is imported
  inside that function — the API enqueues this job and would otherwise load
  torch at startup to do it — and `HF_HOME` is pointed at the models directory
  first, so nothing writes into `~/.cache` or `site-packages`. The extracted
  markdown is written beside the original as `extracted.md`, so a chunker change
  costs no re-parsing.
- **`chunking.py`** is Chonkie's `RecursiveChunker` over markdown levels built
  in code — a section led by its heading, then a paragraph, a line, a sentence,
  a word, and a bare split so a minified line still terminates. Sized in tokens
  against bge-small's own tokenizer, passed as an object rather than a string:
  a string tokenizer routes through `tokie`, which reaches the network even
  when offline is asked for. Each passage carries the line span of its first and
  last characters into `chunks.start_line` / `end_line` for citations.
- **`embedding.py`** runs bge-small-en-v1.5 int8 as a bundled ONNX model on
  `onnxruntime`: tokenize, CLS-pool, L2-normalise, in batches, on this CPU. No
  network, no model server. A reply whose width is not the one `chunk_vectors`
  was built at is refused rather than stored as unrelated numbers.
- **`indexing.py`** replaces a document's chunks and their `chunk_vectors` rows
  in one pass. Re-ingest deletes first, and the delete trigger clears both
  indexes — editing a note stops the old text being findable.
- **Notes reach the worker too.** `POST /documents` and an edit that changes a
  note's content commit and enqueue.
- **torch is pinned to the CPU wheels.** Docling pulls it in, and PyPI's Linux
  build carries 3GB of CUDA an installer would ship to machines that cannot use
  it. `onnxruntime` doubles as RapidOCR's faster backend and the runtime for
  bge-small, so one dependency buys both.

**Dimension `D`** is `SURFSENSE_LOCAL_EMBEDDING_DIMENSION`, default 384 for
bge-small-en-v1.5. `upgrade_to_head` refuses a database whose `chunk_vectors`
was created at another width, so a changed model is caught at startup rather
than by silently mixing unrelated vectors.

## Acceptance

- Note or markdown upload -> `ready`, reachable by both an FTS5 `MATCH` and a
  vec0 nearest-neighbour query. `tests/integration/worker/test_ingest.py` stubs
  the model at the ingest seam so the pipeline runs with no weights on disk;
  one test runs the real encoder and skips when the model directory is absent.
- `test_consumer.py` runs it across two processes: the API enqueues, a real
  `uv run worker.py` picks it up with the bundled model, and the row comes back
  `ready` and searchable. It skips when the model is not fetched.
- Missing file, unloadable model -> `failed` with the reason on the row.
- Re-ingest -> one set of chunks, and the old text gone from the index.
- Serial processing comes from `-w 1` in [`01-boot.md`](01-boot.md).

## Models on disk

`scripts/fetch_embedding_model.py` downloads bge-small (int8 ONNX, tokenizer, config,
~66MB) into `SURFSENSE_LOCAL_MODELS_DIR`, default `~/.surfsense/models/`. CI
runs it before the suite; a release ships the same files as `extraResources`.
`models_dir` is a setting of its own so packaging can point it beside the app.

## Left for Phase 5

A PDF converts, but Docling's first conversion **downloads ~1.6GB of layout and
OCR weights**. `HF_HOME` now lands them under `models_dir`, so nothing writes
into the read-only bundle; the pack still has to ship or be fetched by the
install wizard, which is why nothing in the suite converts a PDF — a test that
downloads is not a test. See [`../api/05-packaging.md`](../api/05-packaging.md).

Docling's default pipeline runs OCR on every PDF, minutes per scanned page on a
CPU. Left on — a scanned PDF is a document a user expects to work — but it is
the first knob to reach for if ingest feels slow.

## Interface from API

Triggered after upload, note creation, note edit and retry —
[`../api/02-upload.md`](../api/02-upload.md).
