# Phase 2 — deepagents adapter over the core

> Build after Phase 1. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md). Shape: [ADR 0002](../../docs/adr/0002-knowledge-core-ports-and-adapters.md).
> The **first driving adapter**: deepagents talking to the framework-agnostic core (`KnowledgeStore`) over the **real git working tree**, replacing the read-side fake (`KBPostgresBackend`). Agent tools are unchanged.
>
> **Status: file-op path implemented (2026-07-28).** Working-copy lifecycle in the core, `GitTreeBackend` adapter, resolver + tool routing behind `KNOWLEDGE_STORE_ENABLED`. Remaining in this phase: the C2 citation envelope on `read_file` (see Work items).

## Objective

Give the agent real file ops (`ls/glob/grep/read/write/edit`) on a **per-turn private worktree** instead of `path_resolver` + a DB folder walk + the `runtime.state` overlay — as a **thin deepagents adapter**, not a bespoke filesystem reimplementation. The adapter is deepagents' own `FilesystemBackend` pointed at the turn's worktree; the core is invoked once, at the end-of-turn commit.

## Locked model

- **This is an adapter, not the core.** The core (`KnowledgeStore`) stays framework-agnostic (imports no deepagents). Only this adapter knows about `BackendProtocol`. It adds no storage logic of its own.
- **In-turn writes live in a per-turn private worktree** (decided 2026-07-28; C6 records this model). Git's own answer to parallel writers: one working tree per writer, never a shared checkout. The worktree is **created lazily on the turn's first KB tool call** (read or write; measured ~90 ms checkout for 500 docs, once per turn) and serves **both reads and writes** for the whole turn — one code path, read-your-own-writes by construction, **no state overlay, no merge logic**. Abort/crash = delete the worktree; a janitor removes orphans.
- **End-of-turn commit = diff, not snapshot.** `porcelain.status(worktree)` (the detached HEAD *is* the base revision) → touched paths → `writes`/`removes` change set → `store.transaction()` under the Redis lock, on top of the current head. Parallel turns' committed work on untouched files is never reverted; same-file overlap is per-file last-writer-wins **with the loser preserved in history**. `ponytail:` ceilings = no three-way merge (upgrade path: git's own), and a mid-turn checkpoint fork/replay does not restore uncommitted worktree files — accepted, no such feature exists.
- **Reuse the existing direct-disk backend; don't reimplement the framework.** Implemented as SurfSense's own `MultiRootLocalFolderBackend` with one mount, `("documents", <working copy>)` — it already ships the whole tool surface (`als_info`/`aread`/`awrite`/`aedit`/`aglob_info`/`agrep_raw`/`alist_tree`/`amove`/`adelete_file`/`armdir`) plus root-confined path resolution, which deepagents' `FilesystemBackend` + `CompositeBackend` would have covered only partially (no move/delete/rmdir/list_tree).
- **Same tool interface.** Upstream `WriteResult`/`EditResult`/`FileInfo`/`GrepMatch` shapes — no extra fields.
- **`path_resolver` path computation retires for flagged workspaces** — folder walk + collision suffixing → real repo paths (filename rules still reused, C1). Keep `DOCUMENTS_ROOT` as the repo-relative prefix for continuity.
- Selected via the resolver behind `KNOWLEDGE_STORE_ENABLED`.

## Citation model — decided 2026-07-28 (full contract: C2)

Raw reads from the worktree; one citation pattern through both doors. Every KB surface (search excerpt or full read) renders as true-document-line-numbered text in one envelope with the handle in the opening tag (`cite="[n]"`); the agent cites `[n:Lx-Ly]` using the line numbers it sees. Registry entries are self-contained `{path, revision, title}` — no chunk ids, markers never enter file bytes. Retires `aload_document`/`render_full_document`'s chunk-render read path for flagged workspaces.

## Work items

1. ✅ **Working-copy lifecycle in the core** (git vocabulary stays behind the port): `open_working_copy` / `diff_working_copy` / `discard_working_copy` / `prune_working_copies` on the port, facade, and engine (`dulwich.worktree`). Copies live at `{root}/.working_copies/{workspace_id}/{copy_id}` (`store_path.py` owns the layout). An **empty store yields a bare directory** (git cannot worktree an unborn HEAD); its diff walks the tree.
2. ✅ New `.../filesystem/backends/git_tree.py` — `GitTreeBackend`: lazy mount of the turn's working copy, **opened on the first KB tool call**. Copy id = `thread-{thread_id}` (langgraph serializes turns per thread; a copy left by a crashed turn is committed with the thread's next turn — recovery semantics; abandoned copies are janitored).
3. ✅ Wired into `resolver.py::build_backend_resolver` behind `KNOWLEDGE_STORE_ENABLED`; mutation tools (`rm`/`rmdir`/`move_file`/`mkdir`) route `GitTreeBackend` down the existing direct-op branches instead of cloud state-staging. Root-cause fix along the way: `mkdir` was a silent no-op on every direct backend while `write` refuses missing parents — added real `mkdir` to `LocalFolderBackend` (+ multi-root passthrough) and made the tool surface backend errors.
4. ⏳ `read_file` C2 citation envelope + normalizer `[n:Lx-Ly]` support (today the flagged path returns the raw line-numbered read with no envelope).
5. ⏳ Janitor scheduling (who calls `prune_working_copies`, e.g. a periodic Celery task) — lands with Phase 3's end-of-turn commit.

## Tests

- ✅ Lifecycle: open at current revision / reopen in place / bare-dir on empty store / isolated parallel copies / net diff (adds, edits, deletes) / discard / age-based prune. (`tests/unit/knowledge_store/`)
- ✅ Adapter: writes land on the turn's copy; tool calls share one copy; committed content readable and deletable; mkdir→write; move; non-`/documents` paths rejected; per-thread isolation. (`tests/unit/middleware/test_git_tree_backend.py`)
- ✅ Resolver returns the git-tree adapter only when the flag is on; falls back to `KBPostgresBackend`/`StateBackend` otherwise.
- ⏳ `read_file` envelope: raw line-numbered file, one `cite="[n]"` handle in the opening tag, no markers in file bytes; normalizer resolves `[n:Lx-Ly]` clamped to the document length at that revision.

## Out of scope

- End-of-turn commit → Phase 3. Index refresh (vector-store-sync consumer) → Phase 4.
- Desktop-local (`MultiRootLocalFolderBackend`) path — unchanged.
- Other adapters (KB REST API, MCP) — deferred (ADR 0002, YAGNI).
