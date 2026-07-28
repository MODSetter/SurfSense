# Phase 1 — Knowledge store core  ✅ implemented

> Build first; every later phase uses this. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
> No agent wiring here — this phase is a standalone, tested versioned-storage service + per-workspace write lock.

## Objective

A `KnowledgeStore` facade that owns one versioned history per workspace and exposes the small, engine-agnostic set of primitives the rest of the pivot needs, with single-writer safety. Engine = **dulwich** (pure Python; no system `git` dependency in the container; real wire protocol so future "bring your own remote" is free), confined behind the facade.

## Locked model

- **One store per workspace**, persistent working tree, at `{FILE_STORAGE_LOCAL_PATH}/knowledge_store/{workspace_id}` (nested **under** the shared blob-store volume so every process sees the same history; see [`00c-shared-contract.md`](00c-shared-contract.md) C1 for filename rules — reuse `path_resolver`'s `safe_filename`/`safe_folder_segment`, keep `.xml`).
- **Markdown/text only** in git; binaries stay in the blob store (Phase-agnostic; see umbrella).
- **Single-writer per store via a Redis lock** keyed `knowledge_store:write_lock:{workspace_id}` — mandatory from v1, **not** an in-process `asyncio.Lock`. The backend runs as multiple OS processes (uvicorn workers + Celery workers), so an in-process lock gives false safety; Redis is already deployed. Token-owned release, 30s TTL, 10s queue-then-fail, and fail-if-Redis-down (a write never proceeds unserialized). `ponytail:` v1 ceiling = one Redis lock held per commit; upgrade path = per-workspace write queue. Full rationale: [`00c-shared-contract.md`](00c-shared-contract.md) C3.
- **dulwich for the hot path**, shell out to `git gc`/repack only for periodic maintenance (not in v1).

## What shipped

1. `dulwich` added to `surfsense_backend` deps.
2. Package `app/knowledge_store/`:
   - `settings.py` — `load_knowledge_store_settings()` (enabled flag + root, from central config).
   - `store_path.py` — `workspace_store_path(workspace_id)`: the sole owner of on-disk layout.
   - `write_lock.py` — `workspace_write_lock(workspace_id)` async context manager over the Redis lock (C3), with explicit TTL/wait constants and `KnowledgeStoreLockError`.
   - `transaction.py` — `Transaction`: the unit-of-work verbs (`write`/`remove`/`move`) and their resolution into concrete writes/removes (`resolve`).
   - `store.py` — `KnowledgeStore` async facade (runs the sync engine via `asyncio.to_thread`; reads are lock-free, writes serialized). Public surface — **intent verbs, no git vocabulary**:
     - First use bootstraps the store — no init ceremony; queries on a virgin store answer empty.
     - `transaction(message, author)` — an atomic unit-of-work scope (SQL `BEGIN`/`COMMIT` shape, Django `transaction.atomic()` precedent) yielding a `Transaction` with verbs `write(path, content)` / `remove(path)` / `move(src, dst)`. On clean exit it records **exactly one revision** under the write lock (`tx.revision` = the new id, `None` if nothing changed); on exception it records nothing. Whether that revision touches one file or fifty is an engine detail.
     - `read_as_of(revision, path)` (temporal read, SQL/Datomic "as of"), `list_revisions(path=None, limit=None)`, `get_current_revision()` (a revision is always a whole-workspace snapshot).
     - Driven-consumer reads (Phase 4's inputs): `list_changes(revision)` — paths added/modified/removed vs the parent, with content ids; `list_paths(revision)` — full enumeration for `reindex`.
     - `compute_content_id(data)` — git blob SHA (content-addressed id, consumed by Phase 4).
   - `engines/base.py` — `VersionedContentEngine` contract (**engine boundary**: `record(writes, removes)`, `read`, `read_as_of`, `list_revisions`, `list_changes`, `list_paths`, `get_current_revision`, `compute_content_id`) + `Revision`/`Change`/`TrackedPath`. `engines/git.py` — `GitContentEngine` (all dulwich mechanics; the swappable engine seam — git vocabulary starts here, not in the port). The verb→snapshot translation lives in the facade, so the batch never surfaces in the API.
3. Config flags `KNOWLEDGE_STORE_ENABLED` (off by default) + `KNOWLEDGE_STORE_ROOT`.

## Tests

Unit (`tests/unit/knowledge_store/`) covers what runs locally for real; anything whose correctness depends on Redis is integration (`tests/integration/knowledge_store/`, real Redis).

- **Engine, unit** (`GitContentEngine` on temp repos): first use bootstraps the store; a mixed write+modify+delete lands in one revision; no-op record returns `None`; removing an untracked path is tolerated; `list_revisions` newest-first, path-scoped, honors `limit`; `list_changes` reports added/modified/removed with content ids; `list_paths` reflects the given revision; revisions carry author + tz-aware timestamp; `compute_content_id` equals real `git hash-object`.
- **Transaction, unit** (pure logic): verbs net into one change set; move resolves from staged or committed content; moving a missing path raises.
- **Facade, integration** (`KnowledgeStore.transaction` + real Redis): one scope records one revision; an exception inside the scope records nothing; a transaction fails cleanly while another writer holds the workspace.
- **Write lock, integration** (real Redis): one writer per workspace; workspaces don't contend; released on scope exit and on exception.

## Out of scope

- Agent/backend wiring → Phase 2. Commit-on-turn → Phase 3. Indexing → Phase 4.
- Structure primitives (`list_tree`/glob/grep) → added in Phase 2. Undo/forward-restore → Phase 4 (v1 is `read_as_of` + `history` only).
- Remotes (push/pull), Git-LFS, `gc`/repack scheduling — deferred (umbrella).

## Resolved (see [`00c-shared-contract.md`](00c-shared-contract.md))

- **Lock:** Redis lock, from v1 (C3) — deploy topology is multi-process, so in-process locks are out.
- **Repo model:** persistent working tree per workspace (C1).
- **Repo root:** `{FILE_STORAGE_LOCAL_PATH}/knowledge_store/{workspace_id}` (C1); backup/retention folds into existing blob-store backup.

## Open questions

1. `gc`/repack scheduling threshold (deferred to a later ops pass, not v1).
