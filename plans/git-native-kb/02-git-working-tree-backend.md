# Phase 2 — Git-working-tree backend

> Build after Phase 1. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
> Replaces the read-side fake (`KBPostgresBackend`) with a backend over the **real git tree**. Agent tools are unchanged.

## Objective

A `GitTreeBackend` implementing deepagents' `BackendProtocol` over the Phase-1 `GitRepoService`, so the agent's `ls/read/write/edit/mv/rm`/`glob`/`grep` operate on real files in the workspace git repo instead of faked-over-Postgres rows.

## Locked model

- **Same tool interface, new backend.** Implement the exact `BackendProtocol` surface `KBPostgresBackend` implements: `als_info`, `aread`, `awrite`, `aedit`, `aglob_info`, `agrep_raw`, `alist_tree_listing` (return the upstream `WriteResult`/`EditResult`/`FileInfo`/`GrepMatch` shapes — no extra fields).
- **Reads hit git; writes stage in the working tree** (commit happens at end of turn — Phase 3). Reuse the same staging/`Command.update` pattern the current wrappers use, but backed by the working tree rather than the `files` cache + Postgres.
- **`path_resolver` retires for flagged workspaces** — virtual `/documents/...` paths become **real repo paths**. Keep `DOCUMENTS_ROOT` as the repo-relative prefix for continuity.
- Selected via the resolver behind `KB_GIT_ENABLED`.

## Work items

1. New `.../filesystem/backends/git_tree.py` — `GitTreeBackend(workspace_id, runtime)` implementing `BackendProtocol` over `GitRepoService`.
   - Map protocol calls → `GitRepoService` primitives (`aread`→`read_file`, `aglob_info`→`list_tree`+`fnmatch`, `agrep_raw`→tree scan, etc.).
   - Preserve read rendering behavior the agent expects (document text/XML view) so reads never regress.
2. Wire into `.../filesystem/backends/resolver.py::build_backend_resolver`: when `KB_GIT_ENABLED` and `workspace_id is not None`, return `GitTreeBackend(workspace_id, runtime)` instead of `KBPostgresBackend`.
3. Gate `path_resolver`/`kb_postgres` usage behind the flag (keep both paths compilable during rollout).

## Tests

- For a seeded repo, `ls`/`read`/`glob`/`grep` return results **identical** to `KBPostgresBackend` for the same content (golden comparison).
- `read` of a nested path returns file content; `glob("**/*.md")` lists the tree; `grep` respects the existing match caps.
- Resolver returns `GitTreeBackend` only when the flag is on; falls back to `KBPostgresBackend`/`StateBackend` otherwise.

## Out of scope

- End-of-turn commit → Phase 3. Index refresh → Phase 4.
- Desktop-local (`MultiRootLocalFolderBackend`) path — unchanged.

## Open questions

1. Read rendering: serve raw markdown from git vs. reproduce the current rendered-document view (citations). Confirm what the agent contract needs.
2. Whether `grep`/`glob` scan the working tree directly or use git plumbing (`git grep` semantics via dulwich) for large repos.
