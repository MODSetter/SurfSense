# Phase 1 — Dedicated Artifact Foundation

**Status:** Implemented on this branch.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md), which is authoritative.
**Goal:** Establish artifact-owned persistence, APIs, Git projection, indexing, retrieval, citations, and the panel contract without coupling artifacts to documents.

## 1. Shipped scope

- Migration `178` creates `Artifact`, `ArtifactFile`, and `ArtifactChunk` persistence.
- Artifact blob storage uses `artifacts/{workspace}/{artifact}/{role}/...`.
- `save_artifact` supports Markdown and the general binary role shape.
- Creates return `artifact_id` and `generation`; revisions require `artifact_id + expected_generation`.
- Dedicated artifact list, manifest, download, immutable-file, chunk-context, and delete routes.
- `/artifacts/**` is a separate Git root projected to `Artifact`, never to `Document`.
- Git-backed indexing is deferred to convergence; non-git indexing runs directly after durable save.
- Hybrid search globally fuses document and artifact candidates.
- Artifact citations use `ARTIFACT_CHUNK` and namespaced frontend IDs.
- The artifact panel, chat cards, library query, and cache keys use `artifact_id`.

Sandbox generation and per-format verification/viewers remain in later phases.

## 2. Persistence

`Artifact` stores title, adapter format, searchable Markdown, stable `/artifacts/...md` path, content hash, generation/index state, ownership/provenance, and timestamps.

`ArtifactFile` stores immutable primary/preview/source blob metadata with one row per role. Source is private.

`ArtifactChunk` stores searchable passages and embeddings independently of document `Chunk`.

Markdown has no file rows. Binary shapes may have primary + source and optionally preview. The schema is format-independent; service coverage includes XLSX-shaped primary + source without shipping XLSX generation.

### Create and revise

- Create allocates a collision-safe `/artifacts/<title>.md` path once.
- Retitle does not move the path.
- Revision row-locks the artifact and rejects a missing or stale `expected_generation`.
- New blobs and file rows replace the generation atomically.
- Rollback removes staged blobs best-effort; commit purges superseded blobs best-effort.
- Git convergence errors are recorded separately and cannot undo a durable artifact. Non-git direct indexing runs in the save transaction; failure rolls back rows and best-effort deletes staged blobs.

## 3. Git and indexing

For Git-backed workspaces, save writes `search_content` into the turn working copy while metadata/blobs become durable in the tool call. The end-of-turn commit projects `/artifacts/**` by `(workspace_id, path)`, then convergence updates `ArtifactChunk` and `indexed_generation`.

For non-git workspaces, the artifact indexing service indexes directly before the save transaction commits. It reuses chunk/embed/cache/reconcile helpers but never connector preparation or document models. Index failure makes the tool fail and rolls back the attempted artifact.

Full-tree convergence covers both `/documents` and `/artifacts`, dispatching each root to its own row and chunk domain. A ready search candidate must have `indexed_generation == generation`.

## 4. API, rendering, and permissions

Artifact APIs live under `/workspaces/{workspace_id}/artifacts`. They enforce `ARTIFACTS_READ` and `ARTIFACTS_DELETE`, workspace ownership, file/artifact ownership, source-file privacy, PDF-only inline disposition, immutable file ETags, and no-store current downloads.

The manifest supplies `artifact_id`, generation, format, searchable Markdown, and visible files. No artifact behavior exists in document `editor-content` or document-file routes.

The frontend panel is keyed by `artifact_id`: no files renders Markdown; files select by primary MIME; unsupported formats fall back to download.

## 5. Search and citations

One query embedding feeds document and artifact candidate queries. Semantic and keyword ranks are globally fused before source grouping and passage limits. Artifact hits remain source-qualified throughout adaptation and reranking.

Artifact chunk citations carry `artifact_id` and `artifact_chunk_id`, serialize as `artifact_chunk_<id>`, resolve through an authenticated artifact route, and open the artifact panel. Overlapping numeric IDs with document chunks are safe.

## 6. Checks

- Atomic create/revise and optimistic-generation conflict coverage.
- Markdown, PDF, DOCX, PPTX, service-level XLSX, and unknown-format persistence shapes.
- Git projection/convergence, stable ID/path, incremental chunk reuse, rebuild, retitle, and removal.
- Non-git direct indexing and indexing-status failure semantics.
- Artifact route RBAC/isolation, ETag/304, no-store download, PDF-only inline, source rejection, and blob purge.
- Mixed-corpus global ranking, one embedding call, namespaced citation parsing/resolution.
- Frontend queries/cards/panel identity use `artifact_id`.

## 7. Exit criteria

1. Artifact success means metadata, current bytes, and (for non-git workspaces) the direct index are durable in-turn.
2. No artifact path creates or adopts a `Document`.
3. Git and non-git workspaces both make artifacts searchable with their documented timing.
4. A stale revision cannot overwrite a newer generation.
5. Delete removes the Git representation where applicable, database ownership rows, chunks, and reachable blobs.
6. Dedicated APIs and citations never rely on document routes or document IDs.
