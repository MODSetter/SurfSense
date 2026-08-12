# Artifacts Overhaul — Authoritative Architecture

**Status:** Dedicated artifact persistence, PDF, DOCX, and PPTX are implemented. Phase 5 (full XLSX skill, verification adapter, and viewer) and phase 6 (legacy report/Typst demolition) remain planned.
**Scope:** Generated non-media deliverables. Media generation remains on its existing pipelines.

This document describes the shipped architecture. The phase documents record delivery scope and must not override these contracts.

## 1. Domain boundary

Generated artifacts are not documents, notes, uploads, or a `DocumentFile` kind. They are a separate domain:

- `Artifact` owns workspace/thread/user provenance, title, adapter `format`, searchable Markdown representation (`search_content`), stable Git path, content hash, generation, indexing generation/status/error, metadata, and timestamps.
- `ArtifactFile` owns one immutable blob for role `primary`, `preview`, or `source`. `(artifact_id, role)` is unique.
- `ArtifactChunk` owns artifact search passages, embeddings, positions, and optional line spans.
- `Document`, `DocumentFile`, and `Chunk` remain the document/upload corpus. No shadow `Document`, `DocumentType.NOTE`, generated document metadata, or artifact adoption into a document row exists.

The separation is deliberate. Documents and artifacts share storage engines, Git revisions, chunking/embedding helpers, and one search surface; they do not share persistence identity or lifecycle semantics.

## 2. Frozen save and manifest contracts

### 2.1 `save_artifact`

Create omits both revision fields. Revision requires both `artifact_id` and `expected_generation`.

```json
{
  "status": "saved",
  "artifact_id": 123,
  "generation": 2,
  "title": "Indian History — Overview",
  "files": [
    {
      "file_id": 456,
      "role": "primary",
      "filename": "indian-history.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "size_bytes": 48213
    },
    {
      "file_id": 457,
      "role": "preview",
      "filename": "indian-history.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 91240
    }
  ]
}
```

- Markdown artifacts have no blob rows; `search_content` is their complete deliverable and download source.
- Binary artifacts require a primary and persisted generation source; a verification-produced preview is included when the adapter has a rendered policy.
- Source files never appear in tool results, manifests, immutable file routes, or user downloads.
- A revision locks the row, compares `expected_generation`, and increments `generation`. A stale writer fails with an instruction to load the source again. A failed revision leaves the current generation intact.
- `load_artifact_source(artifact_id)` returns the stored source and current generation. The next save must pass both identity and generation.
- Failures return a visible failed tool result. There is no end-of-turn persistence promise for metadata or blobs.

### 2.2 Manifest

`GET /api/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/manifest` returns:

```json
{
  "artifact_id": 123,
  "title": "Indian History — Overview",
  "format": "docx",
  "generation": 2,
  "markdown_representation": "Searchable representation…",
  "files": [
    {
      "file_id": 456,
      "role": "primary",
      "filename": "indian-history.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "size_bytes": 48213,
      "content_url": "/api/v1/workspaces/7/artifacts/123/files/456/content"
    }
  ],
  "updated_at": "…"
}
```

The frontend derives text/file rendering from the manifest: no files means read-only Markdown; otherwise the primary MIME selects the viewer. There is no artifact branch in document `editor-content`.

## 3. Persistence and blob lifecycle

Artifact blob keys are owned by the artifact domain:

```
artifacts/{workspace_id}/{artifact_id}/{role}/{uuid}{extension}
```

The artifact storage service reuses configured local/Azure backend interfaces, not document-file models or document key helpers.

- File rows are immutable. Revision stages new blobs, replaces current role rows transactionally, then best-effort purges superseded blobs after commit.
- Rollback best-effort deletes newly staged blobs.
- API deletion removes the Git representation first when Git-backed, commits the row/chunk/file cascade, then best-effort purges captured blob records. Convergence-driven deletion currently best-effort purges blobs before deleting and committing the row.
- A blob deletion failure leaves an unreachable blob and a warning; deletion still proceeds. The inverse failure boundary is not atomic: convergence may delete blobs and then fail its database commit, leaving a surviving file row whose blob is gone. Blob storage cannot enlist in the database transaction; repair is operational rather than rollback.
- Per-file size limits apply independently to primary, preview, and source.
- Only PDF may use inline `Content-Disposition`; all other bytes are attachments. Immutable file routes use checksum ETags and private immutable caching. The stable current download uses `private, no-store`.
- Markdown downloads are generated from current `search_content`.

## 4. Git integration and indexing

Git has two separate projected roots:

```
/documents/**  -> Document + Chunk
/artifacts/**  -> Artifact + ArtifactChunk
```

An artifact create allocates `/artifacts/<normalized title>.md` with collision suffixes. The path is authored once; revisions and retitles reuse it. The path stores only the searchable Markdown representation. Binary artifact bytes remain in blob storage.

### Git-backed workspaces

`save_artifact` durably commits database metadata and blobs inside the tool call and writes the representation into the turn's private working copy. It joins the same one-commit-per-turn revision as document changes.

Commit-time projection dispatches by root. Artifact projection resolves `(workspace_id, path)`, updates the existing `Artifact`, or creates a dedicated Markdown `Artifact` for a direct Git-authored `/artifacts` file; it never adopts or creates a `Document`. Asynchronous convergence indexes the committed representation into `ArtifactChunk`, records `indexed_generation`, and updates indexing status.

Projection/index failure does not invalidate a saved artifact. Pending or failed generations are excluded from artifact search until convergence reaches `indexed_generation == generation`. Full-tree convergence repairs both roots and prunes each domain independently. Artifact removal purges artifact blobs and cascades artifact chunks.

### Non-git workspaces

`ArtifactIndexingService` indexes `search_content` directly in the save transaction. It does not pass through connector/document preparation. An embedding/indexing failure rolls back the artifact rows, restores/removes the working-copy write if any, best-effort deletes staged blobs, and makes the tool fail. This branch remains until workspace Git convergence is universal.

Both paths reuse the existing chunker, embedding cache, embedding batch, and reconciler. Unchanged artifact chunks retain IDs and embeddings across revisions where reconciliation permits.

## 5. Search and citations

Knowledge-base search is one global hybrid ranking over two corpora:

- document candidates from `chunks` joined to `documents`;
- artifact candidates from `artifact_chunks` joined to ready, current-generation `artifacts`.

One query embedding is computed. Semantic and keyword ranks from both corpora are globally fused before grouping and passage caps, so artifacts compete fairly with documents rather than being appended as a second result list. Document filters and mention pins remain document-scoped; workspace/date filtering applies to both where supported.

Retrieval hits carry `source_type` (`document` or `artifact`) and source identity. Artifact citations use `ARTIFACT_CHUNK`, frontend IDs such as `artifact_chunk_<id>`, and locators containing both `artifact_id` and `artifact_chunk_id`. This namespace is mandatory because document and artifact chunk sequences may contain the same numeric ID.

Resolving an artifact citation requires artifact read permission, workspace ownership, ready indexing state, and `indexed_generation == generation`. The citation opens the artifact panel. Document citations are unchanged.

## 6. Artifact API and permissions

Dedicated routes are mounted under `/api/v1/workspaces/{workspace_id}/artifacts`:

- `GET /` — list artifacts;
- `GET /{artifact_id}/manifest`;
- `GET /{artifact_id}/download`;
- `GET /{artifact_id}/files/{file_id}/content`;
- `GET /by-chunk/{artifact_chunk_id}` — citation context;
- `DELETE /{artifact_id}`.

Routes enforce workspace-scoped `ARTIFACTS_READ` or `ARTIFACTS_DELETE`. IDs must belong to the requested workspace and file IDs must belong to the requested artifact. Source-role files always resolve as not found on user-facing content routes.

For Git-backed API deletion, the artifact path is committed as removed before the database row is deleted. A Git removal failure leaves the artifact untouched. If database deletion then fails, later convergence observes the Git removal and deletes the row. Once database deletion commits, best-effort blob purge follows.

## 7. Verification, formats, and format blindness

`verify_artifact(path)` owns structural checking, optional conversion/rasterization/vision review, and the signed receipt. `save_artifact` validates the receipt audience, expiry, adapter, and primary/preview hashes. “Could not visually verify” may be represented in a valid receipt; skipping verification may not.

Persistence is format-blind:

- `Artifact.format` is an adapter-owned string, not a database enum.
- Primary MIME comes from the adapter; unknown formats use the generic adapter and `application/octet-stream`.
- The generic adapter checks non-empty bounded bytes and has no rendered policy.
- Source MIME validation is role-specific and source remains private.
- The manifest and viewer registry degrade unknown or unviewable formats to download.

Shipped formats are Markdown, PDF, DOCX, and PPTX. The dedicated schema and API already support XLSX as primary + source with no preview, and tests prove that shape. Full XLSX authoring, programmatic verification adapter, native grid viewer, and public-share work remain phase 5.

## 8. Rendering and revision UX

The artifact panel and caches are keyed by `artifact_id`. It fetches the dedicated manifest:

- no primary file -> read-only Markdown;
- PDF -> primary in the PDF viewer;
- DOCX/PPTX -> receipt-bound PDF preview;
- unknown/missing preview/oversized/parse failure -> unviewable state with download.

All viewers are read-only. Revisions return to the deliverables agent, which loads the stored source and saves with `artifact_id + expected_generation`. The current manifest is the only product-visible generation; prior file rows/blobs are purged. Git may retain representation history, but it is not an artifact restoration mechanism.

## 9. Delivery status

| Phase | Status | Scope |
|---|---|---|
| 1 | Shipped | Dedicated schema/storage, markdown save, artifact routes, panel, Git root, direct/non-git indexing, dual-corpus search/citations |
| 2 | Shipped | Sandbox and PDF |
| 3 | Shipped | Backend verification service and DOCX |
| 4 | Shipped | PPTX and format-general rendered verification |
| 5 | Planned | XLSX adapter/skill/native viewer and public-share artifact rendering |
| 6 | Planned | Legacy report/resume/Typst demolition and library repoint |

## 10. Phase 6 boundary

Legacy `Report`, report/resume tools, Typst routes, old panels, and historical report rows remain until phase 6. Phase 6 still drops that system without migrating it into either `Artifact` or `Document`; old tool parts become static unavailable cards. This is independent of the already-shipped dedicated artifact architecture.

## 11. Required invariants

1. No artifact operation creates, adopts, updates, or deletes a `Document`.
2. No artifact blob uses document-file models, kinds, routes, or keys.
3. Revision requires matching `artifact_id + expected_generation`.
4. Metadata and blobs are durable before success is returned.
5. Git convergence failure does not roll back a saved artifact; non-git direct indexing failure fails and rolls back the save. Stale indexed generations never search.
6. `/documents` and `/artifacts` project and prune independently.
7. Hybrid rank fusion happens globally across both corpora.
8. Artifact chunk citations remain namespaced from document chunks.
9. Source blobs are never user-readable.
10. XLSX requires no persistence/API schema change; only phase-5 format and viewer work.
