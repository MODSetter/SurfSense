# Phase 4 — Derived Index + Full-Tree Convergence

**Status:** Shipped; extended 2026-08-12 for the dedicated artifact root.
**Umbrella:** [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Converge committed searchable representations into two independent Postgres search domains:

```
documents/** -> Document + Chunk
artifacts/** -> Artifact + ArtifactChunk
```

Incremental and full-tree runs share one planner/body and converge to current HEAD under the workspace index lock. No path crosses domains.

## Current model

- `index_changes` folds net changes since `last_indexed_revision`.
- `index_tree` distrusts the stamp, scans the full tree, and prunes rows whose owned paths disappeared.
- Both dispatch by root and ignore unrelated top-level paths.
- Document projection preserves document IDs and metadata ownership.
- Artifact projection resolves by `(workspace_id, path)`, updates or creates only `Artifact`, and never adopts/creates `Document`.
- Folder reconciliation applies only to the document tree.
- The shared chunker, embedding cache, batch embedder, and reconciler are reused; rows are persisted in domain-specific chunk tables.
- A partial failure withholds the workspace revision stamp so the drift sweep can retry.

## Artifact convergence

Artifact metadata and files were already durable when the representation entered Git. Convergence:

1. resolves the existing artifact by path;
2. updates representation/hash if Git is newer;
3. indexes into `ArtifactChunk`;
4. records `indexed_generation` and `indexing_status=ready`;
5. records a failure without deleting or invalidating the artifact.

Artifact search excludes pending, failed, and stale indexed generations.

On rename within `/artifacts`, the row follows the path and keeps its ID. A cross-domain move is a delete from the old domain and is never an identity conversion. On removal, artifact deletion captures/purges artifact blobs and cascades chunks. Full-tree pruning uses an artifact ownership map independent of document pruning.

## Document convergence

Document paths continue through existing row helpers and `IndexingPipelineService`. Document chunk line spans are stored at cut/reconcile time for citation resolution. Rebuild upserts/prunes rather than wipes so UI-visible document IDs remain stable.

Legacy migration seed adoption remains document-only: seeded document bytes already have their legacy chunk index and begin incremental indexing after the seed revision. New artifacts are never part of that adoption rule because their dedicated rows/index are created by the artifact service.

## Search contract

`search_chunks` preserves the document-only compatibility API for older callers. Agent knowledge-base search uses `search_knowledge_base`, which:

- computes one query embedding;
- queries current document and artifact chunks;
- globally fuses semantic and keyword ranks;
- groups by `(source_type, source_id)`;
- emits namespaced document or `ARTIFACT_CHUNK` citations.

## Queue and recovery

- Post-commit writers enqueue convergence; enqueue failure cannot undo committed content.
- The index lock is separate from the write lock.
- Incremental lock contention retries; redundant full rebuild contention may skip.
- The hourly capped drift sweep compares the workspace stamp with HEAD and re-enqueues convergence.
- Non-git artifact saves bypass this queue and call the artifact indexer inside the save transaction; indexing failure rolls back the attempted save.

## Checks

- Incremental and full-tree runs produce equivalent document and artifact indexes.
- Same numeric IDs across chunk tables do not collide.
- Editing an artifact reuses unchanged chunk IDs/embeddings where reconciliation allows.
- Artifact search requires current indexed generation.
- Rename preserves domain identity; cross-root moves do not convert identity.
- Removing an artifact purges files/chunks; removing a document remains document-only.
- Full rebuild prunes both roots independently and leaves unrelated connector rows untouched.
- One mixed-corpus query embedding and global rank fusion.
- Partial failure withholds the stamp and remains retryable.

## Out of scope

- Live Slack/Gmail connectors.
- Full XLSX authoring/viewer work.
- Legacy report/Typst demolition.
- Merging artifact and document persistence.
