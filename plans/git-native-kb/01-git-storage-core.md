# Phase 1 — Git storage core

> Build first; every later phase uses this. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
> No agent wiring here — this phase is a standalone, testable git service + per-workspace lock.

## Objective

A `GitRepoService` that owns one Git repository per workspace on disk and exposes the small set of primitives the rest of the pivot needs, with single-writer safety. Engine = **dulwich** (pure Python; no system `git` dependency in the container; real wire protocol so future "bring your own remote" is free).

## Locked model

- **One repo per workspace.** Repo path derived from `workspace_id`, rooted alongside the existing blob store (`FILE_STORAGE_LOCAL_PATH` sibling, e.g. `{BASE_DIR}/.kb_git/{workspace_id}`).
- **Markdown/text only** in git; binaries stay in the blob store (Phase-agnostic; see umbrella).
- **Single-writer per repo.** All mutating ops go through a per-workspace lock. `ponytail:` v1 ceiling = one in-process asyncio lock per workspace (upgrade path = Redis lock for multi-worker, see Open questions).
- **dulwich for the hot path**, shell out to `git gc`/repack only for periodic maintenance (not in v1).

## Work items

1. Add `dulwich` to `surfsense_backend` deps (pyproject/requirements) — latest release.
2. New package `app/kb_git/`:
   - `paths.py` — `repo_path(workspace_id)`; ensure-dir helper.
   - `service.py` — `GitRepoService(workspace_id)` with async-friendly wrappers (run dulwich in a threadpool via `asyncio.to_thread`) over:
     - `ensure_repo()` — init if absent.
     - `read_file(path)`, `write_file(path, content)`, `list_tree(prefix)`, `move(src, dst)`, `remove(path)`.
     - `commit(message, author) -> sha`, `log(path=None)`, `read_at(sha, path)`, `revert(sha)`.
     - `blob_sha(path)` (content-addressed id, consumed by Phase 4).
   - `lock.py` — `workspace_lock(workspace_id)` async context manager (per-workspace).
3. Config flag `KB_GIT_ENABLED` (off by default) + repo root setting.

## Tests

- `ensure_repo()` is idempotent; second call no-ops.
- write → `commit` → `log` shows the commit; `read_file` returns content; `read_at(prev)` returns the pre-commit content.
- `move`/`remove` reflected in `list_tree`; `revert(sha)` restores prior state.
- `blob_sha` is stable for identical content and differs after an edit.
- Two concurrent `commit`s on the same workspace **serialize** under the lock (no corruption); different workspaces do not block each other.

## Out of scope

- Agent/backend wiring → Phase 2. Commit-on-turn → Phase 3. Indexing → Phase 4.
- Remotes (push/pull), Git-LFS, `gc`/repack scheduling — deferred (umbrella).

## Open questions

1. Lock granularity: in-process asyncio lock (v1) vs. Redis lock (multi-worker deploys). Confirm deploy topology.
2. Persistent working tree per workspace vs. bare repo + ephemeral checkout per operation (disk vs. speed trade-off).
3. Repo root location relative to blob store + backup/retention implications.
