# Phase 7 — Direct-caller adapter (every non-agent writer)

> **IN PROGRESS (2026-07-31).** Depends on Phases 3/4. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md). Blocks the Phase 5 fleet flip ([`05-migration.md`](05-migration.md), work item 8).

## Objective

One adapter that every non-agent writer calls — routes, Celery tasks, connector
indexers, whatever is written next — so that reaching git is a property of the
operation rather than something each caller has to remember.

## Why now

The canary found four files in the store with no row behind them: the UI delete
drops the row and leaves the file. A rebuild then re-creates the document from
the surviving file and the drift check reports `ok`, having just resurrected
content a user deleted. Flipping real workspaces on that returns deletions.

The route audit that followed found the hole is not one endpoint. Six HTTP paths
reach git (editor save, and the four ingestion flows behind
`prepare_for_indexing`); about twenty do not. Grouped by what they cost a flagged
workspace:

| Class | Paths | Cost |
| --- | --- | --- |
| Deletes | document, note, folder subtree, folder-unlink, folder-sync-finalize, connector delete, workspace delete | File survives; the next rebuild resurrects the document |
| Moves and renames | folder rename, folder move, document move, bulk-move, Obsidian rename | Git keeps the old path; a later save writes the new one, so the content exists twice |
| Creates outside ingestion | note with a body, extension pages, Circleback webhook | Content lives only in Postgres, invisible to git and lost on a rebuild |
| Blind update | `PUT /documents/{id}`, and a `GET` that backfills `source_markdown` | The same, silently |

The count is the finding. Twenty handlers each remembering to call a recorder is
how six ended up wired and twenty did not, and patching twenty of them leaves the
twenty-first — written next month — to fail the same way.

## Locked model

- **Grow `services/document_revision_recorder.py`; do not start a second
  adapter.** It already calls itself the direct-caller adapter and already holds
  the save and ingest verbs. Two half-adapters is the disease, not the cure.
- **The surface is the store's own vocabulary** — save, ingest, remove, move — so
  a caller never writes a git word, and never chooses a path. Path resolution
  stays inside the adapter, where `PATH_MARKER` says where the file actually
  went; recomputing it at the call site is how a delete misses its file.
- **Ordering differs by verb, and has to.** Writes record *after* the Postgres
  commit — the existing rule, content is durable before it is mirrored. Deletes
  and moves record *before* it, because the path is derived from a row that is
  about to stop existing. Both directions converge: a git removal whose row
  delete then fails is repaired by the indexer's own `delete_row`, which is the
  intended end state anyway.
- **A move is `tx.move`, never remove-plus-write.** Phase 4 keeps a document's id
  across a rename by asking dulwich's `RenameDetector`; two unrelated paths in one
  revision reads as a delete and an add, and the id churns — losing citations in
  saved answers and the version rows that cascade from it.
- **Never raises**, like the verbs already there. The two write paths coexist
  until the Phase 5 cut, so a recording failure must not fail a mutation that
  already happened; it is logged and counted through
  `record_knowledge_store_record_outcome`.
- **Core-level bulk deletes are wired by hand.** Connector delete and workspace
  delete issue `sqlalchemy.delete(Document)` statements; no ORM-level hook can
  see them, which is also why a session-event chokepoint was not chosen. A
  workspace delete drops the store outright rather than recording a revision per
  document.

## Work items

Ordered by damage, not by file.

1. ⏳ Adapter verbs: `record_deleted_documents`, `record_moved_documents`, and
   `moves=` on `record_markdown_files` (the low-level verb) so a rename is one
   `tx.move`.
2. ⏳ Wire the deletes: `DELETE /documents/{id}` (via `_delete_document_background`),
   `DELETE /notes/{id}`, `DELETE /folders/{id}` (via `delete_folder_documents_task`),
   `folder-unlink`, `folder-sync-finalize`.
3. ⏳ Wire the bulk deletes: connector delete (a revision removing that
   connector's paths), workspace delete (drop the store).
4. ⏳ Wire the moves: document move, bulk-move, folder rename, folder move,
   Obsidian rename. A folder operation is one revision moving every descendant.
5. ⏳ Wire the creates that skip ingestion: note-with-a-body, extension pages,
   Circleback. These lose content rather than resurrect it, so they rank below
   the deletes.
6. ⏳ `PUT /documents/{id}` — decide whether to wire it or narrow it. It accepts
   arbitrary `DocumentUpdate` fields including `workspace_id`, which is a document
   changing stores; wiring that faithfully is worse than refusing it.

## Tests

- A delete removes the file in the same workspace's store, and a following
  `index_tree` does not bring the document back — the resurrection the canary saw.
- A move keeps the document id, asserted through the indexer, not just the path.
- A folder rename moves every descendant in one revision.
- A workspace delete leaves no store behind.
- Every verb is a no-op on an unflagged workspace, and none of them raise when the
  store is unreachable.

## Out of scope

- The read side: serving document content from git over HTTP. Rows still answer
  reads; this phase is about writes diverging.
- MCP and remote-git adapters (ADR 0002, still deferred).
- Deleting the legacy Postgres write path — that is the Phase 5 cut.

## Open questions

1. Whether a folder rename over a large subtree should be one revision or
   batched. One revision is atomic and matches how git thinks; a 10k-document
   folder makes it a long transaction under the workspace write lock.
2. Whether the soft-tombstone deletes (Obsidian) should remove the file or keep
   it — the row survives by design there, so git removal would disagree with the
   row.

## Sources

- ADR 0002 — ports and adapters; the KB REST API named as a driving adapter.
- Phase 3 `commit_turn.py` — the write-plus-remove transaction shape this mirrors.
- Phase 4 rename churn fix — why a move must be `tx.move`.
