# Phase 1 — Git storage core

> Build first; every later phase uses this. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
> No agent wiring here — this phase is a standalone, testable git service + per-workspace lock.

## Objective

A `GitRepoService` that owns one Git repository per workspace on disk and exposes the small set of primitives the rest of the pivot needs, with single-writer safety. Engine = **dulwich** (pure Python; no system `git` dependency in the container; real wire protocol so future "bring your own remote" is free).

## Locked model

- **One repo per workspace**, persistent working tree, at `{FILE_STORAGE_LOCAL_PATH parent}/.kb_git/{workspace_id}` (see [`00c-shared-contract.md`](00c-shared-contract.md) C1 for the exact layout + filename rules — reuse `path_resolver`'s `safe_filename`/`safe_folder_segment`, keep `.xml`).
- **Markdown/text only** in git; binaries stay in the blob store (Phase-agnostic; see umbrella).
- **Single-writer per repo via a Redis lock** keyed `kb_git:lock:{workspace_id}` — mandatory from v1, **not** an in-process `asyncio.Lock`. The backend runs as multiple OS processes (uvicorn workers + Celery workers), so an in-process lock gives false safety; Redis is already deployed. `ponytail:` v1 ceiling = one Redis lock held per commit; upgrade path = per-workspace write queue. Full rationale: [`00c-shared-contract.md`](00c-shared-contract.md) C3.
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
   - `lock.py` — `workspace_lock(workspace_id)` async context manager over the Redis lock (C3).
3. Config flag `KB_GIT_ENABLED` (off by default) + repo root setting.

## Tests

- `ensure_repo()` is idempotent; second call no-ops.
- write → `commit` → `log` shows the commit; `read_file` returns content; `read_at(prev)` returns the pre-commit content.
- `move`/`remove` reflected in `list_tree`; `revert(sha)` restores prior state.
- `blob_sha` is stable for identical content and differs after an edit.
- Two concurrent `commit`s on the same workspace **serialize** under the Redis lock (no corruption); different workspaces do not block each other. Cover cross-process contention, not just async tasks.

## Out of scope

- Agent/backend wiring → Phase 2. Commit-on-turn → Phase 3. Indexing → Phase 4.
- Remotes (push/pull), Git-LFS, `gc`/repack scheduling — deferred (umbrella).

## Resolved (see [`00c-shared-contract.md`](00c-shared-contract.md))

- **Lock:** Redis lock, from v1 (C3) — deploy topology is multi-process, so in-process locks are out.
- **Repo model:** persistent working tree per workspace (C1).
- **Repo root:** `{blob store parent}/.kb_git/{workspace_id}` (C1); backup/retention folds into existing blob-store backup.

## Open questions

1. `gc`/repack scheduling threshold (deferred to a later ops pass, not v1).
