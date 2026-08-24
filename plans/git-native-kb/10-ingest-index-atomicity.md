# Phase 10 — Ingest→Index Atomicity & One Write Path

**Status:** In progress — A done (`service.py` ingest mark-back). B done (`service.py::_place_unmarked` re-attaches an unmarked row to its own file via `virtual_path_to_doc` instead of authoring `(2)`). C done (`converge.py::_index_one` runs the pipeline `index` in a per-document session so one unindexable file no longer rolls back or crashes its batch-mates). Signup born-flipped done (`users.py::create_default_workspace`).
**Umbrella:** [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Make the document ingest→index path reliable so it stops generating git↔Postgres drift at the source, instead of relying on the drift monitor to mop up. Collapse the two coordinating PG writers (ingest-side and projection-side) into one convergent path where **git is the sole source of truth and Postgres is a pure, self-healing projection**.

## Problem: three durability domains, no shared transaction

A single logical write crosses up to three independently-committed stores under two different locks:

| Domain | Commits | Lock | Site |
|--------|---------|------|------|
| D1 git | content revision | `workspace_write_lock` | `knowledge_store/service.py:188` |
| D2 PG-at-ingest | `documents` row | caller session | `indexing_pipeline/indexing_pipeline_service.py:362` |
| D3 PG-projection | marker + chunks + stamp | `workspace_index_lock` | `knowledge_store/index/converge.py:240` |

No transaction spans D1–D3, so every write path has a failure window. The observed drift (orphan `X (2).md` files, seeder-vs-runtime path disagreement, permanently `missing`/`extra` rows) is the symptom.

## Defects (evidence)

1. **`ingest_documents` writes git, never marks the row.** `service.py:403-448` commits D1 and returns; `Document.path`/`PATH_MARKER` are left for D3 (`index/rows.py:77,88,106`). Until D3 succeeds the row is unmarked; for `pending`/`failed` docs D3 never succeeds, so it is unmarked forever. Unmarked + re-sync re-authors a fresh path against the git tree (`service.py:419,432`) → `(2)…(n)` fork + stranded orphan. Its siblings `save_document` (`:388-394`) and `move_documents` (`:527-532`) already mark; this is the lone omission and the primary drift engine.
2. **`prepare_for_indexing` commits PG before git.** `indexing_pipeline_service.py:340-362` persists+commits the row, then records to git. Truth flows PG→git with a gap; a git failure leaves a marker-less, file-less row.
3. **`converge` rolls back the whole batch on one doc failure.** `IndexingPipelineService.index()` rolls back the shared session on failure (`converge.py:300`), and `failed>0` withholds the stamp (`:230-239`). One bad file can undo earlier upserts in the same run and force a full re-drive.
4. **Two PG writers coexist on flipped workspaces.** `KnowledgeStorePersistenceMiddleware` (git turn commit) and legacy `kb_persistence` are both on the agent stack; the stream fallback can invoke the legacy one.
5. **Path is authored at 3 sites with divergent inputs.** Runtime ingest, `save_document`, and the seeder all call `allocate_path` but with different `taken` (git tree vs recorded PG paths) and possibly different `folder_id` — the seeder-vs-runtime phantom drift.
6. **File upload spans D2→HTTP→Celery→D2→D1.** `routes/documents_routes.py:268-299` inserts a pending row; a later Celery task does `prepare_for_indexing`. A Phase-2 failure strands a pending, unmarked, file-less row.

## Design: git is truth, PG is a projection, path is decided once

Not a distributed transaction (impossible across git+PG). Instead: order the writes against a single source of truth and make the path decision durable as close to the git commit as possible; everything else is rebuildable from git.

- **A — Author once, mark at ingest (keystone).** After `_commit_files` returns a revision, `ingest_documents` writes `path` + `PATH_MARKER` for each doc in the same session commit (mirroring `move_documents`). Re-syncs then reuse the recorded path; pending/failed docs keep their path through a converge failure.
- **B — Re-attach by identity, never re-author.** When a marker is missing, recovery resolves the row to its existing git file by `unique_identifier_hash` (`rows.py:166-181`), never by re-authoring against the tree. Closes the fork even inside A's failure window.
- **C — Isolate converge per document.** Wrap each `_index_one` in a savepoint so one failure cannot roll back the batch, and let the stamp advance for the docs that succeeded.
- **D — One writer, one allocator.** Remove the legacy `kb_persistence` arm from flipped workspaces so only the git recorder writes PG (via projection). Single-home path allocation: one function, one `taken` source (git tree) and one `folder_id` source, shared by ingest + save + seeder, so runtime and seeder cannot disagree.

**Recovery model:** with PG a pure projection, any inconsistency heals by re-projecting git (`index_tree`). The only durable-and-correct requirements are the git revision and the path recorded on the row.

## Adjacent fixes (fold in)

- **Signup born-flipped.** `users.py:166` ignores `KNOWLEDGE_STORE_ENABLED`, so signup default workspaces are born unflipped (316/321 of the current backlog). Set it from config like `workspaces_routes.py:107`.
- **Pending/failed hygiene.** Placeholder rows (`content="Pending..."`, no git file) should be excluded from the drift `desired` set until `ready`, so they stop reading as `missing`.
- **Orphan cleanup.** A one-time `--yes` re-seed removes already-stranded orphans (`seed_workspace` removes tree paths not in the desired set).

## Order (smallest blast radius first)

1. A — mark rows in `ingest_documents`.
2. B — resolve-by-identity guard against forking.
3. C — per-doc savepoints in converge.
4. Signup born-flipped one-liner.
5. D — collapse legacy writer + single-home allocation (largest, last).

## Checks

- A: a connector re-sync of an unchanged file produces no new git path and no orphan (re-ingest is idempotent); the row carries `path`+`PATH_MARKER` immediately after ingest, before any converge.
- B: with the marker cleared on a row whose file exists in git, a re-ingest resolves to the same row/path instead of authoring `X (2).md`.
- C: a batch with one un-indexable doc still projects and stamps the rest; the bad doc is `failed` and retryable.
- D: on a flipped workspace the legacy `kb_persistence` commit is never reached; ingest, save, and seeder derive identical paths for the same row.
- Signup: a new workspace created while `KNOWLEDGE_STORE_ENABLED=true` is born flipped.
- Regression: `tests/integration/knowledge_store/index/test_duplicate_content_convergence.py` still passes (two identical-content files at different paths converge to two rows).

## Out of scope

- Drift-monitor fan-out / visibility-timeout redesign (tracked separately).
- Legacy report/Typst demolition.
- Connector-authoritative (non-`/documents`) rows: Slack, Notion, etc. remain PG-owned and unpruned.
