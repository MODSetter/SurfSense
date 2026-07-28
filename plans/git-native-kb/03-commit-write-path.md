# Phase 3 — Commit-per-turn write path

> Build after Phase 2 (needs the working-tree backend) and Phase 1's `commit`. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Turn staged agent/editor/upload writes into **one atomic git commit** per turn/save, replacing the current "commit staged ops to Postgres" step. This is where the single write path for all indexed content lands.

## Locked model

- **One commit per agent turn.** The commit body is the free function `commit_staged_filesystem_state(...)` in `.../kb_persistence/middleware.py` (called by both `aafter_agent` **and** the stream-task fallback — repoint the function, not just the middleware). For flagged workspaces it becomes: **diff the turn's worktree against its base** (`porcelain.status`, C6) → `writes`/`removes` change set → one `async with KnowledgeStore.transaction(message=…, author=…) as tx:` scope. The scope records exactly one revision on exit and takes the Phase-1 Redis lock internally.
- **No staged-op replay, no ordering pass.** The worktree already holds the netted outcome of the turn (moves are applied file ops; write-then-`rm` nets to nothing), so the state-key drain and its five-step ordering stay on the unflagged legacy path only (C4).
- **Author attribution.** Commit author = `created_by_id` (acting user id already passed to the middleware), or `agent` for autonomous writes; message summarizes the turn's ops.
- **Editor saves & upload-extracted markdown use the same commit path** (one write path). Connector-indexable content (Notion/Drive) commits via the same service on sync.
- **No Postgres content writes here** — chunk/embedding refresh is Phase 4 (triggered off the commit).

## Work items

1. In `commit_staged_filesystem_state`: replace the ordered Postgres write pass with the worktree diff-commit — map `porcelain.status(worktree)` output (untracked → writes, unstaged-present → writes, unstaged-missing → removes) into one `KnowledgeStore.transaction(...)` scope, then drop the worktree. ~15 lines of mapping; no state-key reads.
2. Emit the new commit SHA into state/event so Phase 4's indexer and Phase 6's projector can consume it. Keep the `dispatch_custom_event` (`document_created/updated/deleted`, `folder_deleted`) calls — the UI depends on them.
3. Route editor save (`source_markdown` write) and upload-extracted markdown through a `KnowledgeStore.transaction(...)` scope with a single `tx.write(path, content)` (behind `KNOWLEDGE_STORE_ENABLED`).
4. Remove the now-dead "stage then persist to Postgres" branches for flagged workspaces (keep unflagged path intact during rollout). **Note:** the `DocumentRevision`/`FolderRevision` snapshot code (gated by `flags.enable_action_log`) lives inside this function — its removal is Phase 4; sequence the two together for flagged workspaces.

## Tests

- An agent turn with N file ops produces **exactly one** commit containing the turn's **net** changes (write-then-move lands at the final path; write+rm in one turn creates nothing).
- Editor save produces one commit; commit author (`created_by_id`) + message are correct.
- A failed turn does not leave a partial commit (all-or-nothing) and does not release the lock mid-write.
- The commit SHA is surfaced for downstream consumers (indexer/projector).

## Out of scope

- Building the chunk/embedding index from the commit → Phase 4.
- Zero row projection → Phase 6.

## Resolved (see [`00c-shared-contract.md`](00c-shared-contract.md))

- **Author identity + staged-op state keys:** C4 (both already exist in the current middleware).

## Open questions

1. Commit message format (structured for later `git log` parsing vs. freeform).
2. Squash policy for very chatty turns (one commit per turn is the default; revisit only if noisy).
