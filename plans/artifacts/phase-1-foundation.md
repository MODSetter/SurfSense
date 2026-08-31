# Phase 1 — Artifact Foundation

**Status:** Complete.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md), which is authoritative.
**Goal:** Establish artifact-owned delivery metadata on top of the document corpus — one chunk table, one search leg, one citation namespace — plus the artifact APIs, panel contract, and read-only guards.

## 1. Scope

- Migration `178` adds `DocumentType.ARTIFACT`, creates `artifacts` and `artifact_files`, and links `artifacts.document_id` to `documents` as a non-null unique cascading key.
- Artifact blob storage uses `artifacts/{workspace}/{artifact}/{role}/...`.
- `save_artifact` creates or revises one `Document` + `Artifact` pair, supporting Markdown and the general binary role shape.
- Creates return `artifact_id` and `generation`; revisions require `artifact_id + expected_generation`.
- Artifact list, manifest, download, immutable-file, and delete routes.
- Markdown converges through the existing `/documents` root; no artifact root and no artifact branch in the indexer.
- Hybrid search and citations are the document ones, unchanged.
- The editor refuses to save a document of type `ARTIFACT`; the library shows an artifact badge and type filter.
- The artifact panel, chat cards, and cache keys use `artifact_id`.

Sandbox generation and per-format verification/viewers belong to later phases.

## 2. Persistence

`Document` with `document_type = ARTIFACT` stores the artifact's title, searchable Markdown, `/documents/<title>.md` path, content hash, folder, and indexing status. `document_metadata` carries `artifact_id` so a search hit or citation can route without a second query.

`Artifact` stores adapter `format`, `generation`, workspace/thread/user provenance, originating tool-call ids, verification metadata, timestamps, and `document_id`. It stores no title, path, body, hash, or indexing state — those exist once, on the document.

`ArtifactFile` stores immutable primary/preview blob metadata with one row per role. Generation sources remain transient sandbox inputs.

Markdown artifacts have no file rows. Binary shapes have primary and optionally preview. The schema is format-independent.

### Migration 178

1. Add `ARTIFACT` to the `documenttype` enum.
2. Create `artifacts` with `document_id INTEGER NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE`, `format`, `generation`, provenance columns, `metadata`, and timestamps.
3. Create `artifact_files` with the role uniqueness constraint and blob metadata.
4. Index `artifacts.document_id`, `artifacts.workspace_id`, and `artifacts.thread_id`.

There is no artifact chunk table to create and no artifact search index to build. Downgrade drops both tables; the enum value is left in place, because PostgreSQL cannot drop an enum member and a downgraded database with no artifacts has no rows referencing it.

### Create and revise

- Create allocates a collision-safe `/documents/<title>.md` path through the shared allocator, inserts the document, then the artifact.
- The document is constructed directly rather than through connector preparation, whose corpus-wide content-hash dedup would drop a deliverable whose Markdown matches an existing document.
- Retitle updates the document title and leaves the path alone. A user rename or move goes through the ordinary document move and preserves the document id.
- Revision row-locks the artifact and rejects a missing or stale `expected_generation`.
- New blobs and file rows replace the generation atomically; the document body and hash update in the same transaction.
- Rollback removes staged blobs best-effort; commit purges superseded blobs best-effort.
- The save does not write the knowledge-store path marker. Projection writes it after the revision lands, so a full rebuild never sees a marked document whose file is not committed yet.

## 3. Git and indexing

For Git-backed workspaces, save writes the Markdown into the turn working copy while the document, artifact, and blobs become durable in the tool call. The end-of-turn commit projects `/documents/**` as it does for any document: row upsert resolves by `path`, finds the row the save created, and preserves its Postgres-owned `document_type`. Convergence then chunks and embeds it into `Chunk`.

For non-git workspaces, save calls `IndexingPipelineService.index()` inside the save. Indexing marks the document `processing` and commits mid-flow, so an embedding failure leaves a durable artifact with a `failed` document that the reindex path retries rather than rolling the save back. Losing the deliverable because an embedding provider was down is the worse outcome.

Full-tree convergence has exactly one root and one ownership map. An artifact document is pruned, renamed, and reindexed by the same code as every other document, and its blobs are reached through `artifact.document_id` during purge.

## 4. API, rendering, and permissions

Artifact APIs live under `/workspaces/{workspace_id}/artifacts`. They enforce `ARTIFACTS_READ` and `ARTIFACTS_DELETE`, workspace ownership, file/artifact ownership, PDF/MP4-only inline disposition on immutable content routes, immutable file ETags, and attachment-only no-store current downloads.

The manifest joins the document for title and Markdown and returns `artifact_id`, `document_id`, generation, format, and visible files. `DELETE /{artifact_id}` authorizes as an artifact operation and delegates to document deletion, which owns Git removal, chunk cascade, blob purge, and Zero-visible row state.

Citation context comes from the existing document chunk route. No artifact chunk route exists.

The frontend panel is keyed by `artifact_id`: no files renders Markdown; files select by primary MIME; unsupported formats fall back to download.

`save_document` returns a conflict for a document of type `ARTIFACT`, and the frontend's editable-type set excludes it, so the library can list and open an artifact without offering a save that would desynchronize the Markdown from the bytes it describes.

## 5. Search and citations

Nothing artifact-specific exists in retrieval. One query embedding, one candidate query over `chunks`, one global fusion, one grouping. Artifact documents are ranked, filtered by type, and `@`-mentioned like every other document.

An artifact passage cites as a knowledge-base chunk. Resolution returns the document, its type, and its metadata; the frontend opens the artifact panel when the type is `ARTIFACT` and the document citation panel otherwise. There is no `ARTIFACT_CHUNK` kind, no `artifact_chunk_` marker, and no second numeric sequence to disambiguate.

## 6. Checks

- Atomic create/revise and optimistic-generation conflict coverage.
- Markdown, PDF, DOCX, PPTX, service-level XLSX, and unknown-format persistence shapes.
- A create produces exactly one document with type `ARTIFACT` and one artifact pointing at it.
- Two artifacts with byte-identical Markdown both persist and both index.
- Git projection and convergence preserve `document_type` across incremental and full-tree runs.
- Non-git indexing failure leaves a durable artifact with a failed document that reindex repairs.
- Deleting the artifact removes the Git file, the document, its chunks, the artifact, its file rows, and every reachable blob including artifact roles.
- Artifact route RBAC/isolation, ETag/304, no-store attachment download, and PDF/MP4-only inline content.
- `save_document` refuses an artifact document; rename and move still succeed.
- An artifact passage ranks in the same fusion as documents and its citation opens the artifact panel.
- Frontend queries/cards/panel identity use `artifact_id`.

## 7. Exit criteria

1. Artifact success means the document, artifact, and current bytes are durable in-turn.
2. Every artifact has exactly one document, and no code path creates a second row for the same deliverable.
3. Git and non-git workspaces both make artifacts searchable through the document indexing path with their documented timing.
4. A stale revision cannot overwrite a newer generation.
5. Delete removes the Git file, document/artifact/file rows, chunks, and reachable blobs in one operation.
6. No artifact chunk table, artifact search leg, artifact citation kind, or `/artifacts` root exists anywhere in the codebase.
