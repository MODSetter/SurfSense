# Phase 6 — Zero / real-time projection

> Depends on Phases 3/4. The one genuinely net-new subsystem (partly offsets the deletions). Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Keep the real-time web UI working after git becomes the source of truth. The UI is driven by Zero (Postgres logical replication, `zero_publication.py`); git is not a real-time source, so we project git state → the Zero-published `documents`/`folders` rows after each commit.

## Locked model

- **Two UI channels, both must survive** (see [`00c-shared-contract.md`](00c-shared-contract.md) C5): (1) Zero logical replication of the `documents`/`folders` rows (`zero_publication.py`); (2) the `dispatch_custom_event` SSE (`document_created/updated/deleted`, `folder_deleted`) from the commit path. The projection must keep the rows current **and** the events must keep firing.
- **One-way projection (git → Postgres rows), not a second source of truth.** The projected `documents`/`folders` rows are **thin metadata for the UI** (title, path, folder tree, timestamps) — content authority stays in git; chunks/embeddings stay derived (Phase 4). This preserves the "no two-way sync" rule.
- **Driven by the commit event** (Phase 3). Simplest owner: extend the Phase-4 post-commit indexer to also upsert/delete the Zero-published rows in the same pass (index + project together).
- Zero publication column lists (`zero_publication.py`) stay as-is; we just keep the rows current from git.

## Work items

1. `project_commit(workspace_id, sha)` — from the tree diff, upsert `documents`/`folders` metadata rows and delete rows for removed paths; publish via the existing Zero path.
2. Decide owner: fold into Phase-4 `index_commit` (one post-commit pass) vs. a separate projector task — default: fold in.
3. Ensure ordering: commit → index + project atomically enough that the UI never shows a file with no metadata row (or vice versa).

## Tests

- After a commit, Zero-published `documents`/`folders` rows reflect the new tree within the projection cycle.
- Deleting a file removes its row; renaming updates path/title.
- A workspace with the flag on stays live in the web UI end-to-end (create/edit/delete visible).

## Out of scope

- Replacing Zero with a git-aware sync (not now).
- Frontend changes beyond keeping current behavior (separate umbrella).

## Resolved (see [`00c-shared-contract.md`](00c-shared-contract.md))

- **Projection owner:** fold into the Phase-4 post-commit indexer (index + project one pass) (C5).
- **Both channels preserved:** upsert/delete `documents`/`folders` rows for Zero **and** keep emitting the SSE custom events (C5).

## Open questions

1. Consistency model: index + projection in one pass, or eventually consistent with a short lag (default: one pass).
2. Do any Zero-published columns need content that isn't cheap to derive from the tree (forces a richer projection)?
