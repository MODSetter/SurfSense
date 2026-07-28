# Phase 4 — Derived index + reindex

> Can build alongside Phase 3 (both only need Phase 1's `transaction`/`list_changes`). Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Make Postgres a **derived, rebuildable** chunk/embedding index of the store: incremental on each revision (keyed by content id), fully reproducible via one `reindex(workspace)`. Git history replaces the three hand-rolled versioning systems (their deletion lands at the Phase 5 cut).

## Locked model

- **Post-revision incremental index.** On each revision, `list_changes(revision)` names the changed paths; re-chunk + re-embed only those. **Key embeddings by content id**: unchanged content → same id → reuse existing vectors (no re-embed). This is the correct, native form of what `indexing_pipeline/chunk_reconciler.py::reconcile` already approximates (it matches by chunk *text*; the content id generalizes it to file identity).
- **Postgres is disposable.** A single idempotent **`reindex(workspace)`** wipes chunks/embeddings and rebuilds from the current revision (the Fossil `rebuild` discipline). Search (`shared/retrieval/hybrid_search.py`) is unchanged — it reads the same `chunks` table.
- **History = git; deletion at cut time.** `utils/document_versioning.py` (`DocumentVersion`), `services/revert_service.py` + `DocumentRevision`/`FolderRevision` become dead code for flagged workspaces here, but stay running for unflagged ones. The delete sweep (code + Alembic table drops) is Phase 5, after migration + verification.

## Work items

1. `app/knowledge_store/indexer.py` — `index_revision(workspace_id, revision)`: consume `KnowledgeStore.list_changes(revision)` (shipped: added/modified/removed + content ids), map changed paths→documents/chunks, re-chunk changed files, embed only new content ids, upsert chunks; delete chunks for removed paths. `reindex` enumerates via `list_paths(revision)`.
2. **Store each chunk's `start_line`/`end_line` at cut time** (the chunker is slicing the blob right there). Sole consumer: rendering true document line numbers on search excerpts (C2) — never a stored reference the frontend follows, so rebuilds can't strand it.
3. Blob-SHA reuse is **new** (there is no embedding cache today — `embed_texts` calls the model directly; current reuse is `chunk_reconciler` matching by chunk *text*). Add a `(embedding_model_version, blob_sha)` reuse layer, or generalize the reconciler from chunk-text identity to blob identity. **`content_hash` is workspace-salted, so it is NOT the git blob SHA** — do not alias them. See [`00c-shared-contract.md`](00c-shared-contract.md) C5.
4. `reindex(workspace_id)` — wipe + full rebuild from HEAD; wire a Celery task entrypoint (Celery already runs; keep long rebuilds off the API process).
5. Trigger `index_revision` off Phase 3's surfaced revision id.

## Tests

- Edit one file → only its chunks re-embed; other files' vectors are byte-identical (content-id reuse verified).
- Each chunk's `start_line`/`end_line` matches the exact slice of the blob it was cut from.
- `reindex(workspace)` produces a chunk set identical to the incremental path (determinism).
- Search results for a fixed query match the pre-pivot baseline for the same content.
- Deleting a file removes its chunks; renaming preserves vectors (same content id).

## Out of scope

- Live connectors (Slack/Gmail) — never indexed.
- Zero row projection → Phase 6. Reranker/chunking strategy changes (separate search work).

## Resolved (see [`00c-shared-contract.md`](00c-shared-contract.md))

- **content_hash vs blob SHA:** they differ (content_hash is workspace-salted); key embedding reuse by blob SHA, keep `content_hash` through migration, drop later if redundant (C5).
- **Cache location:** none exists today — the reuse layer is new (C5).
- **Where `reindex` runs:** Celery task (C5).

## Open questions

1. `reindex` progress/observability surface (log vs. status row) — cosmetic, not blocking.
