# Phase 4 — Derived Index + Full-Tree Convergence

**Status:** Shipped.
**Umbrella:** [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Converge committed searchable bodies into one Postgres search domain:

```
documents/** -> Document + Chunk
```

Incremental and full-tree runs share one planner/body and converge to current HEAD under the workspace index lock.

## Current model

- `index_changes` folds net changes since `last_indexed_revision`.
- `index_tree` distrusts the stamp, scans the full tree, and prunes rows whose owned paths disappeared.
- Both ignore top-level paths outside `documents/`.
- Projection preserves document IDs and Postgres-owned metadata, including `document_type`.
- Folder reconciliation applies to the whole document tree.
- The shared chunker, embedding cache, batch embedder, and reconciler are reused; passages land in `Chunk`.
- A partial failure withholds the workspace revision stamp so the drift sweep can retry.

## Convergence

Document paths run through the existing row helpers and `IndexingPipelineService`. Chunk line spans are stored at cut/reconcile time for citation resolution. Rebuild upserts/prunes rather than wipes so UI-visible document IDs remain stable.

Convergence has no notion of document kind. A generated deliverable is a `Document` with `document_type = ARTIFACT`, so it is scanned, chunked, renamed, and pruned by this same body. The one obligation the type creates is negative: upsert resolves by `path` and must never re-derive `document_type` on an existing row, or a rebuild would demote every deliverable to a note. `NOTE` is invented only when creating a row for a git file nothing claims.

An artifact's metadata and blobs were already durable when its Markdown entered Git, so a projection or embedding failure records a failed document and leaves the deliverable intact for reindex; it never deletes an artifact. Removing the file deletes the document, cascades its chunks and artifact sidecars, and purges every reachable blob — `DocumentFile` keys plus `ArtifactFile` keys reached through `artifact.document_id`.

Legacy migration seed adoption remains scoped to seeded bytes: they already have their legacy chunk index and begin incremental indexing after the seed revision. Artifacts are never part of that adoption rule because the artifact service creates their rows with the type already set.

## Search contract

`search_chunks` preserves the compatibility API for older callers. Agent knowledge-base search uses `search_knowledge_base`, which:

- computes one query embedding;
- queries current chunks;
- globally fuses semantic and keyword ranks;
- groups by document;
- emits knowledge-base chunk citations that the frontend routes by `document_type`.

## Queue and recovery

- Post-commit writers enqueue convergence; enqueue failure cannot undo committed content.
- The index lock is separate from the write lock.
- Incremental lock contention retries; redundant full rebuild contention may skip.
- The hourly capped drift sweep compares the workspace stamp with HEAD and re-enqueues convergence.
- Non-git artifact saves bypass this queue and index through `IndexingPipelineService` inside the save; an indexing failure leaves a failed document that reindex repairs.

## Checks

- Incremental and full-tree runs produce equivalent indexes.
- Editing a document or a deliverable reuses unchanged chunk IDs/embeddings where reconciliation allows.
- Incremental and full-tree runs both preserve `document_type` on existing rows; a new git file with no row becomes a `NOTE`.
- Rename preserves identity and keeps a deliverable's artifact sidecar attached.
- Removing a deliverable purges its chunks, artifact rows, and every blob role.
- Full rebuild prunes the one root and leaves unrelated connector rows untouched.
- One query embedding and global rank fusion for the whole corpus.
- Partial failure withholds the stamp and remains retryable.

## Out of scope

- Live Slack/Gmail connectors.
- Full XLSX authoring/viewer work.
- Legacy report/Typst demolition.
