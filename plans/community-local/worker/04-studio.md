# Worker — Phase 4: Studio pipeline

> Owns: `worker/studio/`. Schema: [`../00c-data-model.md`](../00c-data-model.md)
> (`artifacts`), [ADR-0003](../../../docs/adr/0003-artifacts-as-documents.md).

## Goal

`studio_job(artifact_id)` — the selected generation model writes **structured
content** and a trusted **builder** renders the bytes. The Image format is the
one explicit exception: its selected image model returns image bytes through
the OpenAI-compatible Images API. Both paths land as an `ARTIFACT` document +
`artifacts` sidecar + `artifact_files`, `ready` | `failed`.

## Core decision — builders, not a sandbox

Cloud lets the model **author code** and runs it in a network-denied sandbox,
then vision-verifies it and signs a receipt. Local inverts that:

```text
CLOUD   LLM → code → sandbox exec → vision verify → receipt → save
LOCAL   LLM → structured content → trusted builder → save
```

The text model only emits JSON/markdown; a committed per-format function renders
it with a normal library (`python-docx`, `python-pptx`, `XlsxWriter`, …). No
LLM-authored code runs, so there is **no sandbox, no Docker, no receipts** — the
builder output is deterministic and always a valid file. This is why the whole
feature fits the offline, no-Docker, weak-local-model positioning
([`../00-umbrella-plan.md`](../00-umbrella-plan.md)). Image generation is
isolated behind `ImageGenerator`; it is not smuggled through the chat adapter.

## Work

One folder, mirroring `worker/ingestion/`:

- **`pipeline.py`** — engine per job, same shape as
  [`ingestion/pipeline.py`](../../../surfsense_local/backend/worker/ingestion/pipeline.py):
  drive the `ARTIFACT` document `pending → processing → ready | failed`, notify
  on each change ([`../api/04-studio.md`](../api/04-studio.md) `/internal/events`).
  Steps: retrieve context over the chosen documents (`shared/search`) → generate
  the format's structured content (`Generator`) → `build` → write blobs → set
  the document's markdown body and index it through the existing ingest path so
  the artifact is searchable and citable like any other document → `ready`.
- **`generate.py`** — the text LLM step. Prompts the selected generation
  `Generator` (Ollama or an OpenAI-compatible connection) to emit the builder's
  input schema, grounded on the retrieved chunks and optional user prompt. One
  retrieval, format-specific output contract.
- **`media/image.py`** — the Image-only step. Resolves
  `SelectedModel(IMAGE_GENERATION)`, calls `ImageGenerator`, validates and
  normalizes returned bytes, and writes the existing primary artifact file. It
  does not parse `chat/completions` image extensions.
- **`builders/`** — one module per format behind a `BUILDERS` registry keyed by
  the `format` string. Each: `build(spec, sources) -> Built(primary: bytes,
  mime, preview: bytes | None, markdown: str)`. A new format is a builder plus a
  viewer, nothing else branches (`format`-blind persistence, per ADR-0003).

Status lives on the **document**, not the sidecar — `artifacts` has no `status`
column (ADR-0003 keeps indexing state on the `Document`). `generation` on the
sidecar carries revisions; a re-run row-locks and bumps it.

## Format sub-phases (ship in order)

| Sub | Formats | Builder |
|---|---|---|
| **4a** | summary / report | none — markdown **is** the document body, no `artifact_files` |
| **4b** | docx, pptx, xlsx, html, flashcards, quiz, mindmap | `python-docx`, `python-pptx`, `XlsxWriter`, sanitized fragment, JSON + markdown projection, markdown (Markmap rendered client-side) |
| **4c** | pdf | markdown → HTML → PDF (WeasyPrint or ReportLab); bundle native deps like the parser pack |
| **4d** | podcast | two-host script (`Generator`) → **Kokoro-82M** → stitch MP3; Kokoro bundled as a model pack like bge-small |
| **4e** | infographic | generation model emits strict labels, values, hierarchy and style tokens → deterministic SVG/HTML builder + optional PNG preview |
| **4f** | image | selected OpenAI-compatible image model → `/images/generations` → validate and store returned bytes; unavailable without the image role |

4a proves the whole path with zero new deps; each later sub adds one builder (or,
for 4f, one separate image-provider call) against the same pipeline. Video is
outside MVP.

## ADR-0003 obligations the pipeline honours

- The artifact body is a read-only `Document(ARTIFACT)`; save bypasses the
  corpus content-hash dedup (`save_artifact` builds the row directly).
- Blob purge resolves `artifact_files` through `artifact.document_id`, so a
  document delete takes the sidecar and its blobs.
- A revision trails its bytes by one index run — the viewer reads the manifest,
  so what the user opens is always the current generation.

## Acceptance

- Enqueue → blob(s) under `data/workspaces/{id}/artifacts/{id}/` + the document
  `ready` and searchable. Builders are deterministic units — a spec fixture in,
  a valid file out, no model and no network.
- Missing source, generation or build failure → document `failed` with the
  reason on the row; Huey retries.
- Kokoro/PDF packs absent on a machine that lacks them → `failed` with a clear
  reason, mirroring the Docling parser-pack path.
- Infographic fixtures validate the structured schema and deterministic output
  without an image model.
- Image fixtures cover base64 and URL results, MIME and byte limits, timeouts,
  and no automatic retry after a provider may have generated an image.

## Interface from API

`studio_job(artifact_id)` — [`../api/04-studio.md`](../api/04-studio.md). The
same service entry (`create_artifact_job`) is what a future chat tool wraps, so
the worker path is identical for the explicit job and the agentic call.
