# Phase 6 — Zero / real-time projection

> **SHIPPED (2026-07-31), with one deliberate departure from the plan below.** Depends on Phases 3/4. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Keep the real-time web UI working after git becomes the source of truth. The UI is driven by Zero (Postgres logical replication, `zero_publication.py`); git is not a real-time source, so we project git state → the Zero-published `documents`/`folders` rows after each commit.

## Locked model

- **Two UI channels, both must survive** (see [`00c-shared-contract.md`](00c-shared-contract.md) C5): (1) Zero logical replication of the `documents`/`folders` rows (`zero_publication.py`); (2) the `dispatch_custom_event` SSE (`document_created/updated/deleted`, `folder_deleted`) from the commit path. The projection must keep the rows current **and** the events must keep firing.
- **One-way projection (git → Postgres rows), not a second source of truth.** The projected `documents`/`folders` rows are **thin metadata for the UI** (title, path, folder tree, timestamps) — content authority stays in git; chunks/embeddings stay derived (Phase 4). This preserves the "no two-way sync" rule.
- **Driven by the commit event** (Phase 3). ~~Simplest owner: extend the Phase-4 post-commit indexer to also upsert/delete the Zero-published rows in the same pass (index + project together).~~ **Reversed in the build — see below.**
- Zero publication column lists (`zero_publication.py`) stay as-is; we just keep the rows current from git.

## Built as — projection split *out* of the indexer

Phase 4 followed this plan's default and folded the row upsert into the indexer. Rows were therefore correct (the canary's create/move/delete all reached the sidebar) but **late**: `_index_one` upserted the row and then chunked and embedded in the same transaction, committing only at the end, behind a Celery hop. UI freshness was coupled to embedding latency — a note the agent had already committed took seconds to appear, and the legacy path's optimistic overlay could not help because it needs a document id that did not exist yet.

The split undoes exactly that coupling, at the seam `_index_one` already had:

- `app/knowledge_store/index/rows.py` — the row primitives (`upsert_row`, `resolve`, `follow_rename`, `delete_row`, `prune`, `load_owned`, `read_indexable`, `revision_author_id`), lifted out of `converge.py` unchanged so both writers share one notion of identity. Imports no indexing pipeline: the commit path pays this module's import cost on every save.
- `app/knowledge_store/index/project.py` — `project_revision(session, workspace_id, revision)` applies one revision's change list to the rows and returns what it touched. Takes the index lock, and **stands aside** (empty result, no raise) when a rebuild holds it. Deliberately does **not** stamp `last_indexed_revision`: the content is not indexed yet, and claiming otherwise would make the drift sweep skip the workspace.
- `commit_turn.py` — after the revision is durable: project the rows, dispatch `document_created/updated/deleted` naming the real ids, then `enqueue_index` for the slow half. A projection failure is logged and dropped; the indexer converges the same rows either way.

Ordering falls out for free (work item 3): the row is written before any chunk can reference it, never the reverse.

`ensure_folder_hierarchy` moved from `kb_persistence/middleware.py` to `services/folder_service.py` on the way. It was needed by a module the agent package imports (a cycle), and it has to outlive `kb_persistence`, which is deleted at the Phase 5 cut.

## Work items

1. ✅ `project_revision(...)` — from the revision's change list, upsert `documents`/`folders` metadata rows and delete rows for removed paths.
2. ✅ Owner decided — **not** the Phase-4 indexer. Cheap row work runs at commit; expensive chunk/vector work stays async. The indexer keeps its own copy of the same convergence and remains the authority.
3. ✅ Ordering: rows exist before chunks reference them.

## Tests

- `tests/integration/knowledge_store/index/test_project.py` — a committed note has its row with zero chunks behind it; the reported id is the row's id; a second write is an update, not a create; a move keeps the id; a removal drops the row; the stamp is left alone; a following `index_changes` adopts the same row rather than duplicating it; a held index lock makes the projection stand aside.
- `tests/integration/knowledge_store/test_commit_turn.py::test_the_turn_announces_the_rows_it_just_created` — the turn dispatches `document_created` carrying the real row id.

## Out of scope

- Replacing Zero with a git-aware sync (not now).
- Frontend changes beyond keeping current behavior (separate umbrella).

## Resolved (see [`00c-shared-contract.md`](00c-shared-contract.md))

- **Projection owner:** ~~fold into the Phase-4 post-commit indexer (index + project one pass) (C5)~~ — **superseded by the build**: the projection runs at commit time, the indexer keeps converging the same rows. C5's requirement (rows current + events firing) holds; only the owner changed.
- **Both channels preserved:** upsert/delete `documents`/`folders` rows for Zero **and** keep emitting the SSE custom events (C5).

## Known gap — empty folder rows

Neither the indexer nor the projection deletes a `folders` row once its last file leaves the tree, and neither emits `folder_deleted`. Folders are implicit in git (a path, not an object), so nothing in a diff announces that one emptied. Harmless today (an empty folder in the sidebar), and out of this phase; the fix belongs with whoever owns folder lifecycle at the Phase 5 cut.

## Open questions

1. ~~Consistency model: index + projection in one pass, or eventually consistent with a short lag~~ → **two passes**: rows are immediate, chunks are eventually consistent.
2. Do any Zero-published columns need content that isn't cheap to derive from the tree? Not so far — title, folder, path and timestamps all come off the diff.
