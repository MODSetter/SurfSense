# Phase 3 — Commit-per-turn write path

> Build after Phase 2 (needs the working-copy backend) and Phase 1's `transaction`. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Turn the agent turn's working copy — plus editor saves and upload-extracted markdown — into **one atomic revision** per turn/save. This is where the single write path for all indexed content lands.

## Locked model

- **One revision per agent turn.** A new, small persistence middleware (alongside `kb_persistence`, same package area): `aafter_agent` → `diff_working_copy(thread-{id})` → one `KnowledgeStore.transaction` scope replaying the net writes/removes → `discard_working_copy`. Empty diff records nothing. The commit body is a **free function** so the stream-task disconnect fallback (`event_loop.py`) can run the identical routine when `aafter_agent` is skipped — same shape as today's `commit_staged_filesystem_state`.
- **`kb_persistence` is not touched.** Both middlewares coexist behind `KNOWLEDGE_STORE_ENABLED`; the old path keeps serving unflagged workspaces. Deletion of `kb_persistence`, `KBPostgresBackend`, `revert_service`, and the revision models happens at cut time (Phase 5), once every workspace is migrated and verified.
- **Aider-style commit messages.** A weak/fast model generates the message from the turn's diff + chat context (Aider precedent: per-change commits, weak-model messages, Conventional Commits). Trailers carry provenance: `Thread: {id}`.
- **Honest attribution (Aider split).** Author = the acting user; committer = the agent identity. Autonomous writes (no user) author as the agent. Needs a `committer` parameter on `record`/`transaction` (author-only today).
- **Receipts survive, derived from the recorded diff.** KB tools emit provisional receipts; this middleware flips them to `success`/`failed` after `transaction` exits, with the revision id as `external_id`. The diff-of-record is stronger evidence than today's staged-state receipts.
- **No Zero events here.** `document_created/updated/deleted` dispatches move with the derived rows (Phase 4) and projection (Phase 6); flag-on workspaces are dev/test until then.
- **Janitor.** Celery beat task (daily) walks `{root}/.working_copies/*` and calls `prune_working_copies(older_than_seconds=24h)`. 24h far exceeds any turn; crashed-turn copies are reused (and committed) by the thread's next turn well before that. Precedent: git's own prune-by-age (`gc.worktreePruneExpire`), tuned to our copy lifetime.
- **Editor saves & upload-extracted markdown use the same commit path** (one write path): one `transaction` scope with a single `tx.write(path, content)`, behind the flag. Connector-indexable content (Notion/Drive) commits via the same service on sync.
- **No Postgres content writes here** — chunk/embedding refresh is Phase 4 (triggered off the revision).

## Work items

1. New persistence middleware: commit body as a free function (diff → weak-model message → `transaction(message, author, committer)` → receipts → discard); `aafter_agent` wrapper; wire into the flagged middleware stack.
2. Add the `committer` parameter to `record`/`transaction` (defaults to author).
3. Repoint the `event_loop.py` disconnect fallback to the new commit body for flagged workspaces.
4. Surface the new revision id into state/event for Phase 4's indexer and Phase 6's projector.
5. Route editor save and upload-extracted markdown through a `transaction` scope behind the flag.
6. Celery beat janitor task pruning abandoned working copies.

## Tests

- An agent turn with N file ops records **exactly one** revision containing the turn's **net** changes (write-then-move lands at the final path; write+rm in one turn creates nothing).
- A turn that never touches the KB records nothing and pays nothing.
- Editor save records one revision; author = acting user, committer = agent; message present.
- A failed/aborted turn records nothing; the thread's next turn commits the leftover copy (recovery).
- Receipts flip to `success` with the revision id after commit; `failed` on commit error.
- The janitor prunes only copies older than the TTL.

## Out of scope

- Building the chunk/embedding index from the revision → Phase 4.
- Zero row projection → Phase 6.
- Deleting the legacy write path → Phase 5 (cut time).

## Resolved

- Commit message format → Aider-style, weak-model generated, `Thread:` trailer (was open question 1).
- Squash policy → one revision per turn is the model; the working copy nets intra-turn noise by construction (was open question 2).
- Author identity → Aider split (author = user, committer = agent).
