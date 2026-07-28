# Phase 2 — deepagents adapter over the core

> Build after Phase 1. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md). Shape: [ADR 0002](../../docs/adr/0002-knowledge-core-ports-and-adapters.md).
> The **first driving adapter**: deepagents talking to the framework-agnostic core (`KnowledgeStore`) over the **real git working tree**, replacing the read-side fake (`KBPostgresBackend`). Agent tools are unchanged.

## Objective

Give the agent real file ops (`ls/glob/grep/read/write/edit`) on a **per-turn private worktree** instead of `path_resolver` + a DB folder walk + the `runtime.state` overlay — as a **thin deepagents adapter**, not a bespoke filesystem reimplementation. The adapter is deepagents' own `FilesystemBackend` pointed at the turn's worktree; the core is invoked once, at the end-of-turn commit.

## Locked model

- **This is an adapter, not the core.** The core (`KnowledgeStore`) stays framework-agnostic (imports no deepagents). Only this adapter knows about `BackendProtocol`. It adds no storage logic of its own.
- **In-turn writes live in a per-turn private worktree** (decided 2026-07-28; C6 records this model). Git's own answer to parallel writers: one working tree per writer, never a shared checkout. The worktree is **created lazily on the turn's first KB tool call** (read or write; measured ~90 ms checkout for 500 docs, once per turn) and serves **both reads and writes** for the whole turn — one code path, read-your-own-writes by construction, **no state overlay, no merge logic**. Abort/crash = delete the worktree; a janitor removes orphans.
- **End-of-turn commit = diff, not snapshot.** `porcelain.status(worktree)` (the detached HEAD *is* the base revision) → touched paths → `writes`/`removes` change set → `store.transaction()` under the Redis lock, on top of the current head. Parallel turns' committed work on untouched files is never reverted; same-file overlap is per-file last-writer-wins **with the loser preserved in history**. `ponytail:` ceilings = no three-way merge (upgrade path: git's own), and a mid-turn checkpoint fork/replay does not restore uncommitted worktree files — accepted, no such feature exists.
- **Reuse deepagents' built-ins; don't reimplement the framework.** deepagents already ships `FilesystemBackend` (direct-disk) and `CompositeBackend` (prefix routing). Point them at the turn's worktree for the whole `BackendProtocol` surface (`als_info`/`aread`/`awrite`/`aedit`/`aglob_info`/`agrep_raw`/`alist_tree_listing`) rather than hand-rolling any of it.
- **Same tool interface.** Upstream `WriteResult`/`EditResult`/`FileInfo`/`GrepMatch` shapes — no extra fields.
- **`path_resolver` path computation retires for flagged workspaces** — folder walk + collision suffixing → real repo paths (filename rules still reused, C1). Keep `DOCUMENTS_ROOT` as the repo-relative prefix for continuity.
- Selected via the resolver behind `KNOWLEDGE_STORE_ENABLED`.

## Citation model — decided 2026-07-28 (full contract: C2)

Raw reads from the worktree; one citation pattern through both doors. Every KB surface (search excerpt or full read) renders as true-document-line-numbered text in one envelope with the handle in the opening tag (`cite="[n]"`); the agent cites `[n:Lx-Ly]` using the line numbers it sees. Registry entries are self-contained `{path, revision, title}` — no chunk ids, markers never enter file bytes. Retires `aload_document`/`render_full_document`'s chunk-render read path for flagged workspaces.

## Work items

1. **Turn-worktree lifecycle in the core** (git vocabulary stays behind the port): open a detached worktree at the current revision, diff it against its base (`porcelain.status` → change set), drop it on end/abort, janitor orphans (age-based). Grow the port only by what this needs.
2. New `.../filesystem/backends/git_tree.py` — the deepagents adapter: deepagents' `FilesystemBackend` rooted at the turn's worktree, **opened lazily on the first KB tool call** and dropped after the end-of-turn commit (Phase 3 records the worktree's diff through `store.transaction()` under the lock).
3. Wire into `.../filesystem/backends/resolver.py::build_backend_resolver`: when `KNOWLEDGE_STORE_ENABLED` and `workspace_id is not None`, return the git-tree adapter instead of `KBPostgresBackend`.
4. Gate `path_resolver`/`kb_postgres` usage behind the flag (keep both paths compilable during rollout).

## Tests

- For a seeded repo, `ls`/`glob`/`grep`/`list_tree` return results **identical** to `KBPostgresBackend` for the same content (golden comparison).
- `read_file` of a nested path returns the raw line-numbered file in the citation envelope (one `cite="[n]"` handle in the opening tag); the cached/edited file bytes contain **no** citation markers.
- The normalizer resolves `[n:Lx-Ly]` to the registered `{path, revision}` with the emitted lines clamped to the document length at that revision.
- Resolver returns the git-tree adapter only when the flag is on; falls back to `KBPostgresBackend`/`StateBackend` otherwise.

## Out of scope

- End-of-turn commit → Phase 3. Index refresh (vector-store-sync consumer) → Phase 4.
- Desktop-local (`MultiRootLocalFolderBackend`) path — unchanged.
- Other adapters (KB REST API, MCP) — deferred (ADR 0002, YAGNI).
