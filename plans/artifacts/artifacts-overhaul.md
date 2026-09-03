# Artifacts Overhaul — Authoritative Architecture

**Status:** Sandbox generation, backend verification, PDF, DOCX, PPTX, XLSX, interactive HTML, mind maps, unified indexing/search, and phase 9 legacy removal are implemented. Phase 8 specifies interactive flashcards with persisted shared progress; phase 10 completes fallback-format handling, public artifact access, and XLSX hardening; phase 11 specifies interactive quiz artifacts; and phase 12 specifies preset-gated, image-model-generated infographic artifacts.
**Scope:** Generated deliverables. Ordinary media generation remains on its existing pipelines, while current image, podcast, and video flows may record artifact sidecars. Phase 12 reuses the image-generation service to stage infographic bytes into the universal verify-and-save artifact workflow without invoking standalone-image persistence.
**Shape:** [ADR 0003](../../docs/adr/0003-artifacts-as-documents.md) records why a deliverable's body is a document type rather than a second corpus, and the obligations that creates.

This document describes the intended architecture. The phase documents record delivery scope and must not override these contracts.

## 1. Domain boundary

An artifact is a document plus the things a document has no concept of: rendered bytes in one or more roles, an adapter format, an optimistic revision counter, a verification receipt, and the tool-call provenance that produced it. It is not a second corpus.

- `Document` with `document_type = ARTIFACT` owns the artifact's searchable Markdown, title, stable Git path, folder placement, content hash, indexing status, and chunks. It is an ordinary row in the ordinary corpus.
- `Artifact` owns what the document model does not model: adapter `format`, `generation`, workspace/thread/user provenance, the tool-call ids that wrote it, verification metadata, and timestamps. `artifact.document_id` is a non-null unique foreign key with `ON DELETE CASCADE`.
- `ArtifactFile` owns one immutable blob for durable role `primary` or `preview`. Generation sources are transient sandbox inputs. `(artifact_id, role)` is unique.
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
- Binary artifacts require a primary; a verification-produced preview is included when the adapter has a rendered policy.
- Generation sources are not persisted as artifact files and never appear in tool results, manifests, immutable file routes, or user downloads.
- A revision locks the row, compares `expected_generation`, and increments `generation`. A stale writer fails with an instruction to load the latest revision workspace again. A failed revision leaves the current generation intact.
- `load_artifact_for_revision(artifact_id)` restores the current primary, when present, plus Markdown context and the current generation. The next save must pass both identity and generation.
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
- Per-file size limits apply independently to primary and preview.
- PDF and MP4 may use inline `Content-Disposition` on immutable content routes; all other bytes are attachments. The stable current download is always an attachment and uses `private, no-store`.
- Markdown downloads are generated from the document's current Markdown.

## 4. Git integration and indexing

Git has one projected root:

```
/documents/**  ->  Document + Chunk
```

An artifact create allocates `/documents/<normalized title>.md` through the shared path allocator, so it obeys the same filename rules and collision suffixes as any document. The path is authored once; revisions and retitles reuse it. A user who renames or moves the file relocates it through the ordinary document move, which preserves the document id and therefore the artifact. The path stores only the searchable Markdown; binary artifact bytes remain in blob storage.

Artifacts live in the normal visible document tree. They appear in the document list with an artifact badge, are filterable by type, and are `@`-mentionable, because they are documents.

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
- `PATCH /{artifact_id}/flashcard-progress` — phase 8's bounded,
  generation-scoped interaction mutation;
- `DELETE /{artifact_id}`.

Citation context comes from the existing document chunk route, which already returns the document type and metadata the frontend needs to route an artifact citation. Artifacts need no chunk lookup of their own.

Routes enforce workspace-scoped artifact permissions. Reads use
`ARTIFACTS_READ`, progress mutation uses `ARTIFACTS_UPDATE`, and deletion uses
`ARTIFACTS_DELETE`. IDs must belong to the requested workspace and file IDs
must belong to the requested artifact. Only durable primary/preview roles can
exist on user-facing content routes.

`DELETE /{artifact_id}` authorizes as an artifact operation and executes as a document deletion, so Git removal, chunk cascade, blob purge, and Zero-visible row state are handled once, by the code that already owns them.

An artifact's document is read-only through the editor: `save_document` refuses a document whose type is `ARTIFACT` with a conflict, and the frontend's editable-type set excludes it. Rename, move, and delete stay legal — they are metadata operations the document model owns, and the artifact follows its document.

## 7. Verification, formats, and format blindness

`verify_artifact(path)` owns structural checking, optional conversion/rasterization/vision review, and the signed receipt. `save_artifact` validates the receipt audience, expiry, adapter, and primary/preview hashes. “Could not visually verify” may be represented in a valid receipt; skipping verification may not.

Persistence remains format-blind:

- `Artifact.format` is an adapter-owned string, not a database enum.
- Primary MIME comes from the selected adapter.
- Generation sources remain transient sandbox inputs rather than a persistence role.
- The manifest and viewer registry degrade unknown or unviewable formats to download.

Shipped deliverable formats are Markdown, PDF, DOCX, PPTX, XLSX, interactive
HTML, and mind maps. XLSX uses programmatic verification, primary-only
persistence, no preview, and a native read-only grid. HTML uses programmatic
verification and primary-only persistence, is served attachment-only, and
renders client-side in a sandboxed iframe. Mind maps use canonical Markdown
plus a receipt-bound PNG and a format-level Markmap viewer. Image, podcast, and
video flows can also record artifact sidecars through their existing media
pipelines. Phase 8 adds strict JSON flashcards, backend-derived searchable
Markdown, a Motion-powered viewer, and shared generation-scoped marks. Phase 10
adds the fallback adapter for bounded unknown binaries and uses
`application/octet-stream` with attachment-only delivery. Phase 11 adds strict
JSON quizzes, trusted searchable Markdown projection, and per-user
generation-scoped answer state. Phase 12 adds semantic infographic PNGs whose
searchable Markdown is receipt-bound to the visually verified primary, plus a
trusted preset-driven LangGraph interaction before billable generation.

## 8. Rendering and revision UX

The artifact panel and caches are keyed by `artifact_id`. It fetches the dedicated manifest:

- no primary file -> read-only Markdown;
- PDF -> primary in the PDF viewer;
- DOCX/PPTX -> receipt-bound PDF preview;
- XLSX -> primary in the native grid;
- HTML -> primary in a sandboxed iframe (phase 6);
- mindmap -> canonical Markdown in a format-level Markmap viewer, while the
  primary PNG remains the download (phase 7);
- flashcards -> verified primary JSON in a format-level interactive viewer,
  while the document contains a trusted Markdown projection and artifact
  metadata contains bounded shared marks (phase 8);
- quiz -> verified primary JSON in a format-level interactive viewer, while the
  document contains trusted projected Markdown and authenticated answer state
  remains bounded and user-scoped (phase 11);
- infographic -> visually verified primary PNG through the image viewer, while
  receipt-bound Markdown supplies search, citations, accessibility context, and
  revision input (phase 12);
- unknown/missing preview/oversized/parse failure -> unviewable state with download.

All viewers are read-only. Revisions return to the deliverables agent, which loads the current primary plus Markdown context and saves with `artifact_id + expected_generation`. The current manifest is the only product-visible generation; prior file rows/blobs are purged. Git may retain Markdown history, but it is not an artifact restoration mechanism.

## 9. Delivery status

| Phase | Status | Scope |
|---|---|---|
| 1 | Complete | Artifact/file schema and storage, document-backed markdown save, artifact routes, panel, unified indexing, search, and citations |
| 2 | Shipped | Sandbox and PDF |
| 3 | Shipped | Backend verification service and DOCX |
| 4 | Shipped | PPTX and format-general rendered verification |
| 5 | Complete | XLSX skill, programmatic verification, persistence, and authenticated native grid |
| 6 | Complete | Interactive HTML skill, programmatic verification, and a sandboxed-iframe panel viewer |
| 7 | Complete | Markdown-backed interactive mind maps with verified PNG downloads |
| 8 | Planned | Strict JSON flashcards, no-vision verification, Motion viewer, and shared tick/cross progress |
| 9 | Complete | Legacy report/resume/Typst removal and library repoint |
| 10 | Planned | Fallback formats, public artifact access, XLSX hardening, and end-to-end coverage |
| 11 | Planned | Strict JSON single-answer quizzes, trusted Markdown projection, per-user answers and retakes, and one shared authenticated/public viewer |
| 12 | Planned | Preset-gated infographic generation, generic structured-question HITL UI, visual-style prompt recipes, receipt-bound PNG/Markdown verification, and universal artifact persistence |

## 10. Phase 7 mind-map boundary

Phase 7 stores a mind map's canonical hierarchy in the artifact document's
Markdown and a deterministic `.png` as its only primary file and user download.
Explicit `format="mindmap"` metadata selects verification and rendering; the
physical filename does not carry semantic identity. The right panel renders
the Markdown through a format-level Markmap viewer; it does not render or
reverse-engineer the PNG. Programmatic verification binds format, Markdown,
and PNG hashes without a vision pass. The phase adds no editable graph model,
source-file role, export route, or mindmap-specific persistence/API branch.

## 11. Phase 8 flashcard boundary

Phase 8 stores a strict versioned JSON deck as the primary artifact and derives
its searchable Markdown from those exact verified bytes in trusted backend
code. Verification is structural and never enters conversion or vision. The
authenticated format-level viewer uses Motion only for the front/back surface,
shows the shared Spinner until fetch and validation complete, and mounts
unchanged in the desktop panel and mobile Vaul drawer. Tick/cross marks are one
generation-scoped shared map in existing artifact metadata; they do not revise
content, write Git, or reindex. The phase adds no agent tool, database migration,
FSRS state, or review-history model.

## 12. Completed legacy-removal boundary

Phase 9 removed legacy `Report`, report/resume tools, Typst routes, old panels,
and historical report rows without migrating them into `Artifact` or into
artifact documents. Old tool parts now render static unavailable cards. This
remains independent of the artifact architecture above.

## 13. Phase 10 boundary

Phase 10 completes access and fallback behavior around the existing model. A
compatibility public primary-content route already serves current media cards;
phase 10 adds token-scoped manifest, download, and per-file reads, not public
artifact copies. It also adds a fallback adapter, not persistence suffix
branches, and XLSX hardening, not spreadsheet editing. Public snapshots
allowlist artifact IDs and resolve the current generation. Flashcards reuse the
same viewer publicly but do not expose or mutate authenticated shared marks.
Generation sources remain transient and are never publicly readable.

## 14. Phase 11 quiz boundary

Phase 11 stores one strict versioned quiz JSON file as the primary artifact and
derives its searchable Markdown from those exact verified bytes in trusted
backend code. Explicit `format="quiz"` selects quiz verification and rendering;
generic JSON and flashcard JSON never acquire quiz semantics from MIME or
suffix inference. The authenticated viewer persists only the current user's
generation-scoped submitted answers and retake scope in bounded artifact
metadata, while public interaction stays visit-local. Scoring, review, retake
missed, and retake all derive from the verified answer key without an attempt
history, persisted score, new table, public mutation API, or dedicated quiz
agent tool.

## 15. Phase 12 infographic boundary

Phase 12 stores one normalized PNG as
`Artifact(format="infographic")` and binds it through the verification receipt
to the searchable Markdown containing its factual content and hierarchy.
Physical `image/png` does not confer infographic behavior: ordinary generated
images remain `format="image"` and mind-map downloads remain
`format="mindmap"`.

Before billable generation,
`load_artifact_instructions(artifact_type="infographic")` deterministically
emits a checkpointed `structured_question` interrupt backed by the immutable
`infographic.visual-style.v1` preset. A generic non-modal question renderer
appears above the composer and submits stable option IDs through the existing
resume path. The agent neither authors nor chooses whether to ask these
questions, and phase 12 registers no agent-facing `ask_user` tool.

The resolved visual-style recipe is compiled into the image-model prompt by
trusted backend code. Infographic generation reuses the lower-level workspace
image-model, billing, provider, and byte-normalization service, but it never
calls the standalone image tool's persistence branch or creates an extra image
artifact/card. The staged PNG proceeds through the universal
verify-then-`save_artifact` workflow with one bounded regeneration after visual
verification findings. The phase adds no infographic-specific persistence
model, save tool, panel, search leg, citation kind, or public route.

## 16. Required invariants

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
11. Generation sources are transient sandbox inputs and never become artifact blobs.
12. New formats require an adapter and optional viewer, not a persistence or API schema change.
13. Public artifact routes reuse the manifest model and expose only allowlisted primary/preview files.
14. When a format renders one durable representation but downloads another,
    verification binds both inputs so the panel and downloaded artifact cannot
    silently diverge.
15. Adapter-owned Markdown projection is derived only from receipt-bound primary
    bytes; the agent cannot provide a competing representation.
16. Mutable artifact interaction state is bounded, generation-scoped, and
    separate from content revision, Git projection, and indexing.
17. Physical suffix and MIME never select semantic JSON or PNG behavior;
    `Artifact.format` and its signed verification receipt do.
18. Structured-question origin is server-owned metadata. Preset questions are
    immutable and bounded, browser responses contain stable IDs only, and an
    agent cannot claim preset origin.
19. Infographic generation may reuse the lower-level image-generation service,
    but it cannot invoke standalone-image persistence or create a second
    `Artifact(format="image")`.
