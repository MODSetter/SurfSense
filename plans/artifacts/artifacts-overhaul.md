# Artifacts Overhaul — Authoritative Architecture

**Status:** Sandbox generation, backend verification, PDF, DOCX, and PPTX are implemented. The persistence, indexing, and search model in sections 1, 3, 4, and 5 is under implementation. Phase 5 (full XLSX skill, verification adapter, and viewer) and phase 6 (legacy report/Typst demolition) remain planned.
**Scope:** Generated non-media deliverables. Media generation remains on its existing pipelines.
**Shape:** [ADR 0003](../../docs/adr/0003-artifacts-as-documents.md) records why a deliverable's body is a document type rather than a second corpus, and the obligations that creates.

This document describes the intended architecture. The phase documents record delivery scope and must not override these contracts.

## 1. Domain boundary

An artifact is a document plus the things a document has no concept of: rendered bytes in one or more roles, an adapter format, an optimistic revision counter, a verification receipt, and the tool-call provenance that produced it. It is not a second corpus.

- `Document` with `document_type = ARTIFACT` owns the artifact's searchable Markdown, title, stable Git path, folder placement, content hash, indexing status, and chunks. It is an ordinary row in the ordinary corpus.
- `Artifact` owns what the document model does not model: adapter `format`, `generation`, workspace/thread/user provenance, the tool-call ids that wrote it, verification metadata, and timestamps. `artifact.document_id` is a non-null unique foreign key with `ON DELETE CASCADE`.
- `ArtifactFile` owns one immutable blob for role `primary`, `preview`, or `source`. `(artifact_id, role)` is unique.
- `Chunk` is the only passage table. There is no artifact chunk table, no artifact embedding column, and no artifact search index.

Single ownership is the point. Title, path, body, and indexing state exist once — on the document — so a rename is one write with one outcome instead of two rows that can disagree. Format, generation, roles, and receipts exist once, on the artifact, because no plain document needs them. Type is the only discriminator: it selects a badge, participates in the type filter, and gates the editor's read-only guard. Nothing in storage, indexing, retrieval, or citation branches on it.

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

- Markdown artifacts have no blob rows; the document's Markdown is their complete deliverable and download source.
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
  "document_id": 4821,
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

Title and `markdown_representation` are read from the joined document, which is their only home. The frontend derives text/file rendering from the manifest: no files means read-only Markdown; otherwise the primary MIME selects the viewer. There is no artifact branch in document `editor-content`.

## 3. Persistence and blob lifecycle

Artifact blob keys are owned by the artifact domain:

```
artifacts/{workspace_id}/{artifact_id}/{role}/{uuid}{extension}
```

The artifact storage service reuses configured local/Azure backend interfaces, not document-file models or document key helpers. Binary bytes never enter Git and never become `DocumentFile` rows.

- File rows are immutable. Revision stages new blobs, replaces current role rows transactionally, then best-effort purges superseded blobs after commit.
- Rollback best-effort deletes newly staged blobs.
- Deletion is the document deletion path. The route marks the document `deleting`; the purge task records the Git removal before the row disappears, then cascades chunks, the artifact, and its file rows, and purges every reachable blob. Marking first drops the artifact out of search immediately, and removing the file before the row is the only safe order — a committed file that outlives its row is read back on the next rebuild as a document nobody asked for.
- Blob purge covers artifact roles as well as document files: the purge query collects `DocumentFile` keys for the document and `ArtifactFile` keys through `artifact.document_id`, so no reachable blob depends on the caller knowing which kind of document it deleted.
- A blob deletion failure leaves an unreachable blob and a warning; deletion still proceeds. Blob storage cannot enlist in the database transaction, so repair is operational rather than rollback.
- Per-file size limits apply independently to primary, preview, and source.
- Only PDF may use inline `Content-Disposition`; all other bytes are attachments. Immutable file routes use checksum ETags and private immutable caching. The stable current download uses `private, no-store`.
- Markdown downloads are generated from the document's current Markdown.

## 4. Git integration and indexing

Git has one projected root:

```
/documents/**  ->  Document + Chunk
```

An artifact create allocates `/documents/Artifacts/<normalized title>.md` through the shared path allocator, so it obeys the same filename rules and collision suffixes as any document. The path is authored once; revisions and retitles reuse it. A user who renames or moves the file relocates it through the ordinary document move, which preserves the document id and therefore the artifact. The path stores only the searchable Markdown; binary artifact bytes remain in blob storage.

The `Artifacts/` folder is a normal visible folder. Artifacts appear in the document list with an artifact badge, are filterable by type, and are `@`-mentionable, because they are documents.

### Git-backed workspaces

`save_artifact` durably commits the document row, the artifact row, and the blobs inside the tool call, and writes the Markdown into the turn's private working copy. It joins the same one-commit-per-turn revision as document changes.

Commit-time projection and convergence treat the file as what it is — a document. Row upsert resolves by `path`, finds the row the save already created, and never re-derives `document_type`, so the type chosen at save survives every projection and every full rebuild. A Markdown file authored directly in Git under `/documents` with no row claiming it is a note; nothing can promote a file to an artifact, because only `save_artifact` creates the sidecar.

The save deliberately does not write the knowledge-store path marker. The marker means "the indexer owns this file", and a marker on a document whose file has not been committed yet reads to a full rebuild as an orphan to prune. Projection writes the marker once the revision lands.

### Non-git workspaces

`save_artifact` indexes the Markdown through `IndexingPipelineService.index()` inside the save. It constructs the document row directly rather than going through connector preparation, whose corpus-wide content-hash dedup would silently discard a second artifact whose Markdown matches an existing document — correct for a re-synced Notion page, wrong for a deliverable with its own identity, roles, and generation.

An indexing failure records a failed document status and leaves the artifact and its blobs intact; the document reindex path retries it. The artifact is not searchable until that succeeds, and it is never destroyed by an embedding outage.

Both paths reuse the existing chunker, embedding cache, embedding batch, and reconciler. Unchanged passages retain ids and embeddings across revisions where reconciliation permits.

## 5. Search and citations

Knowledge-base search is one hybrid ranking over one corpus. An artifact's passages are candidates exactly like any other document's: same `chunks` join, same semantic and keyword legs, same reciprocal-rank fusion, same per-source passage caps. Document type filters and mention pins apply to artifacts too — an artifact can be pinned with `@` and excluded by type, neither of which a parallel corpus allowed.

Citations are one namespace. An artifact passage cites as a knowledge-base chunk with a `{document_id, chunk_id}` locator, and chunk ids are unambiguous because there is one sequence. Resolving a citation returns the document with its type and metadata; `ARTIFACT` opens the artifact panel keyed by the `artifact_id` carried in `document_metadata`, and every other type opens the document citation panel. No artifact-specific citation kind, marker prefix, or resolution route exists.

An artifact is excluded from search under exactly the conditions that exclude a document: while its status is `deleting`, and before its first index completes. A revision's passages therefore trail its blob by one convergence run on Git-backed workspaces — the same staleness window every edited document has, and the reason the panel reads the manifest rather than the index.

## 6. Artifact API and permissions

Dedicated routes are mounted under `/api/v1/workspaces/{workspace_id}/artifacts`:

- `GET /` — list artifacts;
- `GET /{artifact_id}/manifest`;
- `GET /{artifact_id}/download`;
- `GET /{artifact_id}/files/{file_id}/content`;
- `DELETE /{artifact_id}`.

Citation context comes from the existing document chunk route, which already returns the document type and metadata the frontend needs to route an artifact citation. Artifacts need no chunk lookup of their own.

Routes enforce workspace-scoped `ARTIFACTS_READ` or `ARTIFACTS_DELETE`. IDs must belong to the requested workspace and file IDs must belong to the requested artifact. Source-role files always resolve as not found on user-facing content routes.

`DELETE /{artifact_id}` authorizes as an artifact operation and executes as a document deletion, so Git removal, chunk cascade, blob purge, and Zero-visible row state are handled once, by the code that already owns them.

An artifact's document is read-only through the editor: `save_document` refuses a document whose type is `ARTIFACT` with a conflict, and the frontend's editable-type set excludes it. Rename, move, and delete stay legal — they are metadata operations the document model owns, and the artifact follows its document.

## 7. Verification, formats, and format blindness

`verify_artifact(path)` owns structural checking, optional conversion/rasterization/vision review, and the signed receipt. `save_artifact` validates the receipt audience, expiry, adapter, and primary/preview hashes. “Could not visually verify” may be represented in a valid receipt; skipping verification may not.

Persistence is format-blind:

- `Artifact.format` is an adapter-owned string, not a database enum.
- Primary MIME comes from the adapter; unknown formats use the generic adapter and `application/octet-stream`.
- The generic adapter checks non-empty bounded bytes and has no rendered policy.
- Source MIME validation is role-specific and source remains private.
- The manifest and viewer registry degrade unknown or unviewable formats to download.

Shipped formats are Markdown, PDF, DOCX, and PPTX. The schema and API already support XLSX as primary + source with no preview, and tests prove that shape. Full XLSX authoring, programmatic verification adapter, native grid viewer, and public-share work remain phase 5.

## 8. Rendering and revision UX

The artifact panel and caches are keyed by `artifact_id`. It fetches the dedicated manifest:

- no primary file -> read-only Markdown;
- PDF -> primary in the PDF viewer;
- DOCX/PPTX -> receipt-bound PDF preview;
- unknown/missing preview/oversized/parse failure -> unviewable state with download.

All viewers are read-only. Revisions return to the deliverables agent, which loads the stored source and saves with `artifact_id + expected_generation`. The current manifest is the only product-visible generation; prior file rows/blobs are purged. Git may retain Markdown history, but it is not an artifact restoration mechanism.

## 9. Delivery status

| Phase | Status | Scope |
|---|---|---|
| 1 | In progress | Artifact/file schema and storage, document-backed markdown save, artifact routes, panel, unified indexing, search, and citations |
| 2 | Shipped | Sandbox and PDF |
| 3 | Shipped | Backend verification service and DOCX |
| 4 | Shipped | PPTX and format-general rendered verification |
| 5 | Planned | XLSX adapter/skill/native viewer and public-share artifact rendering |
| 6 | Planned | Legacy report/resume/Typst demolition and library repoint |

## 10. Phase 6 boundary

Legacy `Report`, report/resume tools, Typst routes, old panels, and historical report rows remain until phase 6. Phase 6 drops that system without migrating it into `Artifact` or into an artifact document; old tool parts become static unavailable cards. This is independent of the artifact architecture above.

## 11. Required invariants

1. One artifact is one document. `artifact.document_id` is non-null and unique, and no artifact operation creates a second row for the same deliverable.
2. Title, path, Markdown, and indexing state live only on the document. Format, generation, roles, and receipts live only on the artifact.
3. No artifact blob uses document-file models, kinds, routes, or keys.
4. Revision requires matching `artifact_id + expected_generation`.
5. Metadata and blobs are durable before success is returned.
6. An indexing failure never destroys a saved artifact; it records a failed document status and stays retryable.
7. `/documents` is the only projected root, and convergence contains no artifact branch.
8. One chunk table, one search leg, one global rank fusion.
9. One citation namespace; document type decides which panel a citation opens.
10. An artifact document is not editable through the editor, and the guard is enforced server-side.
11. Source blobs are never user-readable.
12. XLSX requires no persistence/API schema change; only phase-5 format and viewer work.
