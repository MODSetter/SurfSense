# Phase 4 — Derived index + reindex

> **Unblocked.** Phase 1's `list_changes`/`list_paths`/`read_as_of` and Phase 3's write path both shipped. Nothing here depends on C2 — the dependency runs the other way: C2's excerpt render consumes work item 2's line spans, and its own four pieces (envelope, registry, normalizer, resolver) stay out of scope here. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
>
> **Why this matters now:** for flagged workspaces `kb_persistence` no-ops (`middleware/stack.py:250-252` leaves the state overlay empty), so agent notes are committed to git and **have no document rows, chunks, or embeddings at all** — invisible to search. This phase closes that gap.

## Objective

Make Postgres a **derived, rebuildable** chunk/embedding index of the store: incremental on each revision (keyed by content id), fully reproducible via one `reindex(workspace)`. Git history replaces the three hand-rolled versioning systems (their deletion lands at the Phase 5 cut).

## Locked model

- **Post-revision incremental index.** On each revision, `list_changes(revision)` names the changed paths; re-chunk + re-embed only those. **Key embeddings by content id**: unchanged content → same id → reuse existing vectors (no re-embed). This is the correct, native form of what `indexing_pipeline/chunk_reconciler.py::reconcile` already approximates (it matches by chunk *text*; the content id generalizes it to file identity).
- **Identity is the path, and it already lines up.** `compute_identifier_hash` (`indexing_pipeline/document_hashing.py`) and `generate_unique_identifier_hash` (`utils/document_converters.py`) build the same `{type}:{unique_id}:{workspace_id}` string, so a synthetic `ConnectorDocument(document_type=NOTE, unique_id=<virtual path>)` yields the identity the legacy path and `virtual_path_to_doc` already use. This is why Phase 4 is a **thin adapter over the existing pipeline**, not a second pipeline.
- **One convergence function, two callers.** `index_revision` and `reindex` differ only in which paths they pass and which rows they prune — they share the body. Determinism between the incremental and rebuild paths is then structural, not something a test hopes for.
- **Document rows converge; they are never wiped.** `documents` and `folders` are in the Zero publication (`alembic/versions/116_create_zero_publication.py`), so their ids reach the browser. A rebuild upserts by `unique_identifier_hash` and deletes only rows whose path left the tree; wiping and recreating would make every note vanish and reappear with new ids. **Chunk rows are the disposable layer**, replaced per document by the existing pipeline.
- **Everything stored must be derivable from git.** Anything threaded in from a caller (notably `created_by_id`) is erased by the next `reindex`, making the two paths disagree. Derive the actor from the revision author instead — `knowledge_store/identities.py::user_identity` encodes it as `<id>@users.surfsense`.
- **Postgres is disposable.** A single idempotent **`reindex(workspace)`** rebuilds the index from the current revision (the Fossil `rebuild` discipline). Search (`shared/retrieval/hybrid_search.py`) is unchanged — it reads the same `chunks` table.
- **History = git; deletion at cut time.** `utils/document_versioning.py` (`DocumentVersion`), `services/revert_service.py` + `DocumentRevision`/`FolderRevision` become dead code for flagged workspaces here, but stay running for unflagged ones — proven by a test, not by inspection (see Tests). The delete sweep (code + Alembic table drops) is Phase 5, after migration + verification.

## Work items

1. `app/knowledge_store/indexer.py` — `index_revision(workspace_id, revision)` and `reindex(workspace_id)` over one shared `_converge(...)`. Paths come from `list_changes` / `list_paths` (shipped: added/modified/removed + content ids), content from `read_as_of`; each document is upserted then handed to `IndexingPipelineService.index()` wrapped in a synthetic `ConnectorDocument`. Removed paths drop their document row (chunks cascade).
   **Bypass `prepare_for_indexing`.** It silently drops a *new* path whose content matches an existing document and marks an *edited* one `failed("Duplicate content")` (`indexing_pipeline_service.py:279-311`). `cp a.md b.md` is legal in git and must yield two indexed documents — path is identity, content is not unique. Model the upsert on `kb_persistence/middleware.py::_create_document` and reuse its `ensure_folder_hierarchy` for folder rows.
2. **Store each chunk's `start_line`/`end_line` at cut time.** Sole consumer: rendering true document line numbers on search excerpts ([`00c-shared-contract.md`](00c-shared-contract.md) C2) — never a stored reference the frontend follows, so rebuilds can't strand it. Bigger than it looks, and the **only** piece C2 needs from this phase:
   - Alembic migration adding both columns to `chunks` (neither exists today).
   - `chunk_text` discards chonkie's `start_index`/`end_index` (`document_chunker.py:19`), and `chunk_text_hybrid`'s `.strip()` destroys the offset mapping — absolute offsets need `segment_start + stripped_prefix + chunk.start_index`.
   - **Spans live in the cached value**, not recomputed downstream: they are a pure function of the cache's existing key (`markdown_sha256 + chunker_kind + chunker_version`), so a `chunker_version` bump is the whole invalidation story. Recovering offsets later by searching the source for chunk text is ambiguous whenever a document repeats a line (boilerplate, table rows).
3. ~~Add a blob-SHA reuse layer~~ — **already shipped.** `indexing_pipeline/cache/cached_indexing.py::build_chunk_embeddings` caches the summary vector and every chunk vector under `EmbeddingKey(markdown_sha256, embedding_model, embedding_dim, chunker_kind, chunker_version)`: content-addressed, no workspace salt, i.e. the content id this phase wanted, and `index()` already routes through it. The legacy note path (`kb_persistence/middleware.py:235-239`) calls `chunk_text`/`embed_texts` directly and bypasses the cache, which is likely why it was believed missing. C5 still holds: **`content_hash` is workspace-salted, so it is NOT a content id** — do not alias them.
4. `reindex(workspace_id)` behind a Celery task (mirror `knowledge_store_janitor_task.py`; register in `app/celery_app.py`). Serialize per workspace with an **index lock distinct from the write lock**: the write lock's 30s TTL is sized for a commit, and reusing it would stall agent writes behind embedding calls.
5. Trigger `index_revision` off Phase 3's surfaced revision id, at **both** writers (`commit_turn.py`, `services/document_revision_recorder.py`). Enqueue-only, never raising — the content is already committed either way.
6. **Self-healing drift, not a deploy step.** A new `workspaces.last_indexed_revision` makes `last_indexed_revision != get_current_revision()` a drift predicate; a daily Beat task enqueues `reindex` for drifted flagged workspaces. That one mechanism covers the initial backfill of already-flagged workspaces (they have git content and no index today), a lost Celery task, a crashed worker, and any workspace flagged later. Runbook steps get forgotten; converging systems don't.

## Tests

- **Identical content at two paths yields two documents** — the case `prepare_for_indexing` gets wrong, and the reason the upsert is hand-written.
- Edit one file → only its chunks re-embed; an untouched file's chunk rows keep the same ids and byte-identical vectors (content-id reuse verified).
- Each chunk's `start_line`/`end_line` matches the exact slice of the blob it was cut from — including a document whose text repeats, and one containing a Markdown table (the hybrid chunker's strip path).
- `reindex(workspace)` produces a chunk set identical to the incremental path (determinism), and leaves document ids unchanged.
- Re-running `index_revision` on an already-stamped revision is a no-op.
- Deleting a file removes its document and chunks; renaming preserves vectors (same content id → cache hit, no model call).
- **Search parity is differential, not a golden baseline.** Index identical content through the connector pipeline and through the git indexer; assert a fixed query returns the same documents in the same order. A stored baseline rots the first time the chunker or embedding model changes, and then someone deletes the test.
- **A save in a flagged workspace creates zero `DocumentVersion` / `DocumentRevision` rows** — turns the locked model's dead-code claim into an enforced invariant before Phase 5 drops the tables under it. `routes/documents_routes.py` also writes versions; confirm whether that path is flag-gated.
- Unit: a synthetic `ConnectorDocument`'s hash equals `generate_unique_identifier_hash(NOTE, virtual_path, workspace_id)`. The whole adapter rests on two formulas in separate modules agreeing.

## Out of scope

- Live connectors (Slack/Gmail) — never indexed.
- Zero row *projection* (folder/document rows driven from the tree as a first-class concern) → Phase 6. Note this is not the same as the existing publication: `documents`/`folders` already replicate, which is why rebuild stability is in the locked model rather than deferred.
- C2's envelope, citation registry, `[n:Lx-Ly]` normalizer, and `read_as_of` resolution — Phase 2's remaining work item, unblocked by this phase's line spans.
- Reranker/chunking strategy changes (separate search work).

## Resolved (see [`00c-shared-contract.md`](00c-shared-contract.md))

- **content_hash vs blob SHA:** they differ (content_hash is workspace-salted); key embedding reuse by a content id, keep `content_hash` through migration, drop later if redundant (C5).
- **Cache location:** ~~none exists today~~ — corrected: `indexing_pipeline/cache/cached_indexing.py`, keyed by `markdown_sha256` + model + chunker. Work item 3 is a call site, not a build (C5).
- **Where `reindex` runs:** Celery task (C5).
- **Rebuild granularity:** document rows converge (upsert + prune); only chunk rows are wiped. `documents`/`folders` are in the Zero publication, so their ids reach the browser and must be stable across a rebuild.
- **Rename semantics:** a rename lands as removed + added, so the document gets a new path-derived identity and a fresh row; vectors survive via the content-addressed cache. Accepted — path is identity, and rows are derived data.

## Open questions

1. `reindex` progress/observability surface (log vs. status row) — cosmetic, not blocking.
