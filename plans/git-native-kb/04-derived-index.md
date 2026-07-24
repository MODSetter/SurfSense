# Phase 4 — Derived index + reindex

> Can build alongside Phase 3 (both only need Phase 1's `commit`/`log`). Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Make Postgres a **derived, rebuildable** chunk/embedding index of the git repo: incremental on each commit (keyed by blob SHA), fully reproducible via one `reindex(workspace)`. Delete the three hand-rolled versioning systems — git history replaces them.

## Locked model

- **Post-commit incremental index.** On each commit, diff the tree against the parent, and for changed blobs re-chunk + re-embed. **Key embeddings by git blob SHA**: unchanged blob → same SHA → reuse existing vectors (no re-embed). This is the correct, native form of what `indexing_pipeline/chunk_reconciler.py::reconcile` already approximates (it matches by chunk *text*; blob SHA generalizes it to file identity).
- **Postgres is disposable.** A single idempotent **`reindex(workspace)`** wipes chunks/embeddings and rebuilds from git HEAD (the Fossil `rebuild` discipline). Search (`shared/retrieval/hybrid_search.py`) is unchanged — it reads the same `chunks` table.
- **History = git.** Delete `utils/document_versioning.py` (`DocumentVersion`), `services/revert_service.py` + `DocumentRevision`/`FolderRevision` (Alembic migration to drop tables). `git log`/`diff`/`revert`/`blame` replace them.

## Work items

1. `app/kb_git/indexer.py` — `index_commit(workspace_id, sha)`: tree-diff parent→sha, map changed paths→documents/chunks, re-chunk changed files, embed only new blob SHAs, upsert chunks; delete chunks for removed paths.
2. Blob-SHA cache key: reuse/extend the embedding cache to `(model_version, blob_sha)`; feed `chunk_reconciler` blob identity so unchanged content keeps vectors.
3. `reindex(workspace_id)` — wipe + full rebuild from HEAD; wire a CLI/task entrypoint.
4. Trigger `index_commit` off the Phase-3 commit event.
5. Delete the three versioning systems + Alembic migration dropping `document_versions`, `document_revisions`, `folder_revisions`.

## Tests

- Edit one file → only its chunks re-embed; other files' vectors are byte-identical (blob-SHA reuse verified).
- `reindex(workspace)` produces a chunk set identical to the incremental path (determinism).
- Search results for a fixed query match the pre-pivot baseline for the same content.
- Deleting a file removes its chunks; renaming preserves vectors (same blob SHA).
- Post-migration: version/revert endpoints and tables are gone; no import references remain.

## Out of scope

- Live connectors (Slack/Gmail) — never indexed.
- Zero row projection → Phase 6. Reranker/chunking strategy changes (separate search work).

## Open questions

1. Collapse `documents.content_hash` onto blob SHA vs. keep both through migration (see umbrella Open items).
2. Where `reindex` runs (Celery task vs. sync admin command) and its progress/observability.
