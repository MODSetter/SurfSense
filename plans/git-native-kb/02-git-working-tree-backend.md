# Phase 2 — Git-working-tree backend

> Build after Phase 1. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
> Replaces the read-side fake (`KBPostgresBackend`) with a backend over the **real git tree**. Agent tools are unchanged.

## Objective

A `GitTreeBackend` implementing deepagents' `BackendProtocol` over the Phase-1 `GitRepoService`, so the agent's `ls/glob/grep`/structure comes from the **real git tree** instead of the `path_resolver` + DB folder walk — **without regressing `read_file`'s chunk-level citations** (see [`00c-shared-contract.md`](00c-shared-contract.md) C2).

## Locked model

- **Same tool interface, new backend.** Implement the exact `BackendProtocol` surface `KBPostgresBackend` implements: `als_info`, `aread`, `awrite`, `aedit`, `aglob_info`, `agrep_raw`, `alist_tree_listing` (return the upstream `WriteResult`/`EditResult`/`FileInfo`/`GrepMatch` shapes — no extra fields).
- **Structure from git; `read_file` content still renders from chunks (v1).** `als_info`/`aglob_info`/`alist_tree_listing`/existence read the git working tree. But `read_file` today renders XML from `Chunk` rows and registers `[n]` citations (`aload_document` → `render_full_document`) — v1 **keeps that render path** (sourced from the derived chunks, one-way from git) so citations don't regress. `grep` may scan working-tree source directly (its matches are already coarse `<chunk-match>` snippets). See C2.
- **Writes stage in the working tree** (commit at end of turn — Phase 3). Reuse the current staging/`Command.update` pattern, backed by the working tree rather than the `files` cache.
- **`path_resolver` path computation retires for flagged workspaces** — folder walk + collision suffixing is replaced by real repo paths (filename rules still reused, C1). Keep `DOCUMENTS_ROOT` as the repo-relative prefix for continuity.
- Selected via the resolver behind `KB_GIT_ENABLED`.

## Work items

1. New `.../filesystem/backends/git_tree.py` — `GitTreeBackend(workspace_id, runtime)` implementing `BackendProtocol` over `GitRepoService`.
   - Structure calls → `GitRepoService` primitives (`als_info`/`alist_tree_listing`→`list_tree`, `aglob_info`→`list_tree`+`fnmatch`, `agrep_raw`→working-tree scan).
   - `read_file`/`aread`/`aedit` existence + content: **reuse the existing chunk-render path** (`aload_document`/`render_full_document`) so `[n]` citations are unchanged in v1.
2. Wire into `.../filesystem/backends/resolver.py::build_backend_resolver`: when `KB_GIT_ENABLED` and `workspace_id is not None`, return `GitTreeBackend(workspace_id, runtime)` instead of `KBPostgresBackend`.
3. Gate `path_resolver`/`kb_postgres` usage behind the flag (keep both paths compilable during rollout).

## Tests

- For a seeded repo, `ls`/`glob`/`grep`/`list_tree` return results **identical** to `KBPostgresBackend` for the same content (golden comparison).
- `read_file` of a nested path returns the rendered document view and registers the **same `[n]` citations** as the Postgres backend (no citation regression).
- Resolver returns `GitTreeBackend` only when the flag is on; falls back to `KBPostgresBackend`/`StateBackend` otherwise.

## Out of scope

- End-of-turn commit → Phase 3. Index refresh → Phase 4.
- Desktop-local (`MultiRootLocalFolderBackend`) path — unchanged.
- **Raw-git-blob reads with per-document citations** — deferred (C2); revisit with the `raw/`+`wiki/` content model.

## Resolved (see [`00c-shared-contract.md`](00c-shared-contract.md))

- **Read rendering:** structure from git, `read_file` content keeps the chunk-render + citation path in v1 (C2).
- **glob/grep source:** working-tree scan via `GitRepoService` (dulwich plumbing optimization deferred).
