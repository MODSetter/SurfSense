# Phase 3 — Commit-per-turn write path

> Build after Phase 2 (needs the working-tree backend) and Phase 1's `commit`. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Turn staged agent/editor/upload writes into **one atomic git commit** per turn/save, replacing the current "commit staged ops to Postgres" step. This is where the single write path for all indexed content lands.

## Locked model

- **One commit per agent turn.** Repoint `KnowledgeBasePersistenceMiddleware` (`.../main_agent/middleware/kb_persistence/middleware.py`, `aafter_agent`) from "write folders/documents/chunks to Postgres" to "flush staged working-tree ops → `GitRepoService.commit(message, author)`" under the Phase-1 per-workspace lock.
- **Author attribution.** Commit author = the acting user (or `agent` for autonomous writes); message summarizes the turn's ops.
- **Editor saves & upload-extracted markdown use the same commit path** (one write path). Connector-indexable content (Notion/Drive) commits via the same service on sync.
- **No Postgres content writes here** — chunk/embedding refresh is Phase 4 (triggered off the commit).

## Work items

1. In `kb_persistence/middleware.py`: replace the ordered Postgres write pass with a `GitRepoService.commit(...)` of the staged tree ops (create/write/edit/move/rm/mkdir already tracked in state).
2. Emit the new commit SHA into state/event so Phase 4's indexer and Phase 6's projector can consume it.
3. Route editor save (`source_markdown` write) and upload-extracted markdown through `GitRepoService.write_file` + commit (behind `KB_GIT_ENABLED`).
4. Remove the now-dead "stage then persist to Postgres" branches for flagged workspaces (keep unflagged path intact during rollout).

## Tests

- An agent turn with N file ops produces **exactly one** commit containing all N changes (atomic).
- Editor save produces one commit; commit author + message are correct.
- A failed turn does not leave a partial commit (all-or-nothing).
- The commit SHA is surfaced for downstream consumers (indexer/projector).

## Out of scope

- Building the chunk/embedding index from the commit → Phase 4.
- Zero row projection → Phase 6.

## Open questions

1. Commit message format (structured for later `git log` parsing vs. freeform).
2. Squash policy for very chatty turns (one commit per turn is the default; revisit only if noisy).
