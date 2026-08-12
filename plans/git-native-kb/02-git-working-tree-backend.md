# Phase 2 — deepagents adapter over the core

> Build after Phase 1. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md). Shape: [ADR 0002](../../docs/adr/0002-knowledge-core-ports-and-adapters.md).
> The **first driving adapter**: deepagents talking to the framework-agnostic core (`KnowledgeStore`) over the **real git working tree**, replacing the read-side fake (`KBPostgresBackend`). Agent tools are unchanged.
>
> **Status: file-op path implemented (2026-07-28); flip-safe as of 2026-07-30.** Working-copy lifecycle in the core, `GitTreeBackend` adapter, resolver + tool routing behind `KNOWLEDGE_STORE_ENABLED`. The C2 citation envelope on `read_file` is **deferred to its own post-flip PR** — it is not a flip blocker; what was, the `read_file` description promising a citation envelope the git path never renders, is fixed (see work item 4).

## Objective

Give the agent real file ops (`ls/glob/grep/read/write/edit`) on a **per-turn private worktree** instead of `path_resolver` + a DB folder walk + the `runtime.state` overlay — as a **thin deepagents adapter**, not a bespoke filesystem reimplementation. The adapter is deepagents' own `FilesystemBackend` pointed at the turn's worktree; the core is invoked once, at the end-of-turn commit.

## Locked model

- **This is an adapter, not the core.** The core (`KnowledgeStore`) stays framework-agnostic (imports no deepagents). Only this adapter knows about `BackendProtocol`. It adds no storage logic of its own.
- **In-turn writes live in a per-turn private worktree** (decided 2026-07-28; C6 records this model). Git's own answer to parallel writers: one working tree per writer, never a shared checkout. The worktree is **created lazily on the turn's first KB tool call** (read or write; measured ~90 ms checkout for 500 docs, once per turn) and serves **both reads and writes** for the whole turn — one code path, read-your-own-writes by construction, **no state overlay, no merge logic**. Abort/crash = delete the worktree; a janitor removes orphans.
- **End-of-turn commit = diff, not snapshot.** `porcelain.status(worktree)` (the detached HEAD *is* the base revision) → touched paths → `writes`/`removes` change set → `store.transaction()` under the Redis lock, on top of the current head. Parallel turns' committed work on untouched files is never reverted; same-file overlap is per-file last-writer-wins **with the loser preserved in history**. `ponytail:` ceilings = no three-way merge (upgrade path: git's own), and a mid-turn checkpoint fork/replay does not restore uncommitted worktree files — accepted, no such feature exists.
- **Reuse the existing direct-disk backend; don't reimplement the framework.** Implemented as SurfSense's own `MultiRootLocalFolderBackend` with one mount, `("documents", <working copy>)` — it already ships the whole tool surface (`als_info`/`aread`/`awrite`/`aedit`/`aglob_info`/`agrep_raw`/`alist_tree`/`amove`/`adelete_file`/`armdir`) plus root-confined path resolution, which deepagents' `FilesystemBackend` + `CompositeBackend` would have covered only partially (no move/delete/rmdir/list_tree).
- **Same tool interface.** Upstream `WriteResult`/`EditResult`/`FileInfo`/`GrepMatch` shapes — no extra fields.
- **`path_resolver` path computation retires for flagged document workspaces** — folder walk + collision suffixing → real repo paths (filename rules still reused, C1). The repo has one projected root. `GitTreeBackend` mounts the working copy's `documents/` subtree for generic KB file tools, and the artifact service writes deliverable bodies inside it (`documents/Artifacts/`) through the same path allocator while owning its own API and blob lifecycle. Commit projection therefore has one row/chunk domain to maintain.
- Selected via the resolver behind `KNOWLEDGE_STORE_ENABLED`.

## Citation model — decided 2026-07-28 (full contract: C2)

Raw reads from the worktree; one citation pattern through both doors. Every KB surface (search excerpt or full read) renders as true-document-line-numbered text in one envelope with the handle in the opening tag (`cite="[n]"`); the agent cites `[n:Lx-Ly]` using the line numbers it sees. Registry entries are self-contained `{path, revision, title}` — no chunk ids, markers never enter file bytes. Retires `aload_document`/`render_full_document`'s chunk-render read path for flagged workspaces.

## Work items

1. ✅ **Working-copy lifecycle in the core** (git vocabulary stays behind the port): `open_working_copy` / `diff_working_copy` / `discard_working_copy` / `prune_working_copies` on the port, facade, and engine (`dulwich.worktree`). Copies live at `{root}/.working_copies/{workspace_id}/{copy_id}` (`store_path.py` owns the layout). An **empty store yields a bare directory** (git cannot worktree an unborn HEAD); its diff walks the tree.
2. ✅ New `.../filesystem/backends/git_tree.py` — `GitTreeBackend`: lazy mount of the turn's working copy, **opened on the first KB tool call**. Copy id = `thread-{root thread}` (langgraph serializes turns per thread; a copy left by a crashed turn is committed with the thread's next turn — recovery semantics; abandoned copies are janitored). **The copy is scoped to the turn, not to the actor**: subagents run under a namespaced `{parent}::task:{tool_call_id}` thread id (one segment per nesting level), so `thread_working_copy_id` resolves the root segment and every actor in the turn — orchestrator and nested subagents alike — shares one copy. That is also what keeps one turn to one revision, which the receipts and citation revisions assume. `open_working_copy` serializes its check-then-create behind a module lock, so parallel subagents reopen rather than race.
3. ✅ Wired into `resolver.py::build_backend_resolver` behind `KNOWLEDGE_STORE_ENABLED`; mutation tools (`rm`/`rmdir`/`move_file`/`mkdir`) route `GitTreeBackend` down the existing direct-op branches instead of cloud state-staging — as do `write_file`/`edit_file`, which stage as a side effect of a successful write and were missed in the first pass (see the canary findings below). Root-cause fix along the way: `mkdir` was a silent no-op on every direct backend while `write` refuses missing parents — added real `mkdir` to `LocalFolderBackend` (+ multi-root passthrough) and made the tool surface backend errors.
4. ⏳ `read_file` C2 citation envelope + normalizer `[n:Lx-Ly]` support (today the flagged path returns the raw line-numbered read with no envelope).

   **Flip-safety split off and shipped (2026-07-30); the envelope itself is deferred to its own post-flip PR.** The envelope is not a flip blocker — search citations are unaffected, since `search_knowledge_base` reads the `chunks` rows the indexer writes and resolves through `/documents/by-chunk/{id}` unchanged. The *description* was: `select_description` ignored its `mode` argument and told every mode that reads come back as `<document … view="full">` with `[n]`-labelled passages, adding "cite the same `[n]` you would use from `search_knowledge_base`". Only `KBPostgresBackend` renders that envelope, so on a flipped workspace the model was promised labels it never sees while holding search ordinals in context — a mis-citation surface (right ordinal, wrong source), which is worse than the missing citation it looks like. Now split by read format rather than by cloud-vs-desktop: the envelope text for cloud-on-Postgres, and a raw-file text that forbids reusing a search ordinal for everything else. This **also fixed desktop-local**, which had carried the same wrong description since before the flag existed. `knowledge_store_enabled` threads `stack.py` → subagent deps → `build_filesystem_mw` → middleware, and already keys the compiled-graph cache.

   Remaining, as a separate PR, in four slices: (1) the envelope + registry entries carrying `{path, revision, title, numbered}` + normalizer `[n:Lx-Ly]` parsing with a fail-closed strip; (2) the line range carried through to a new payload, a `read_as_of` resolution endpoint, and the frontend panel — **this slice is cross-stack**, since `surfsense_web` resolves citations only by numeric chunk id today and C2's currency is `(path, revision, lines)`; (3) search excerpts through the same envelope using the stored spans; (4) the span-fill job for legacy `NULL`-span chunks. Slices 3 and 4 *depend on* the flip: spans exist only where the git indexer has run, and C2 defines the fill job as flipped-only, matching against the git blob because post-flip that is the source of truth.
5. ✅ Janitor scheduling — shipped with Phase 3: daily Celery beat task via `knowledge_store/janitor.py` (see [`03-commit-write-path.md`](03-commit-write-path.md)).

## Canary findings (2026-07-30)

The first live agent turn on the canary workspace exposed two defects in the same write path, neither of which the suite caught.

**A delegated write never reached git.** The subagent wrote into copy `thread-21::task:call_x` while the end-of-turn commit, which only ever knows the parent thread, diffed `thread-21`. `diff_working_copy` raised `FileNotFoundError`, the commit returned `None` silently, and the copy leaked because `discard_working_copy` was never reached. Delegation is the normal path for agent writes, so most writes were affected. Fixed by scoping the copy to the turn's root thread (item 2). The tests missed it because all of them build the copy id by hand — `open_working_copy(f"thread-{THREAD_ID}")` — so none exercised the two sides *deriving* the id from a thread. The regression test now writes through `GitTreeBackend` with a `::task:` runtime and commits with the parent id.

**The legacy path silently covered for it.** `write_file` and `edit_file` set `dirty_paths` under `is_cloud` with no backend check, so `kb_persistence` recorded the same write into Postgres (`creates=1` in the turn log) and the document appeared in the UI. That masked the first defect — nothing errored — and fixing the copy id alone would have converted the silent loss into double writes: one revision plus a legacy document git never hears about. `dirty_paths` is one of five keys the legacy commit triggers on (with `staged_dirs`, `pending_moves`, `pending_deletes`, `pending_dir_deletes`); with all six mutating tools guarded, none is reachable under the git backend, so the legacy commit is a true no-op on a flipped workspace. `files` stays — it is the in-turn read cache, not a trigger.

Canary fallout was one Postgres-only document and one orphaned worktree. The worktree was discarded; the document needs no repair, since the seeder adopts it into git on the next flip.

## Tests

- ✅ Lifecycle: open at current revision / reopen in place / bare-dir on empty store / isolated parallel copies / net diff (adds, edits, deletes) / discard / age-based prune. (`tests/unit/knowledge_store/`)
- ✅ Adapter: writes land on the turn's copy; tool calls share one copy; a subagent's write is visible to the orchestrator; committed content readable and deletable; mkdir→write; move; non-`/documents` paths rejected; per-thread isolation. (`tests/unit/middleware/test_git_tree_backend.py`)
- ✅ A delegated write (namespaced `::task:` thread id) lands in the parent turn's revision, and its copy is discarded rather than orphaned. (`tests/integration/knowledge_store/test_commit_turn.py`)
- ✅ `write_file`/`edit_file` stage nothing for the legacy commit under the git backend, while a workspace still on the old path keeps staging. (`tests/unit/middleware/test_git_tree_tool_staging.py`)
- ✅ Resolver returns the git-tree adapter only when the flag is on; falls back to `KBPostgresBackend`/`StateBackend` otherwise.
- ⏳ `read_file` envelope: raw line-numbered file, one `cite="[n]"` handle in the opening tag, no markers in file bytes; normalizer resolves `[n:Lx-Ly]` clamped to the document length at that revision.
- ✅ `read_file` description matches what each mode returns: cloud-on-Postgres is told about the `view="full"` envelope, while git-native **and desktop** are told their reads carry no `[n]` and must not reuse a search ordinal. (`tests/unit/middleware/test_read_file_description.py`)

## Out of scope

- End-of-turn commit → Phase 3. Index refresh (vector-store-sync consumer) → Phase 4.
- Desktop-local (`MultiRootLocalFolderBackend`) path — unchanged.
- Other adapters (KB REST API, MCP) — deferred (ADR 0002, YAGNI).
