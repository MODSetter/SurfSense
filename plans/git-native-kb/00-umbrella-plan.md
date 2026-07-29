# Git-native Knowledge Base — Umbrella Plan

> Master roadmap for pivoting the Knowledge Base from the custom virtual-filesystem-over-Postgres to **Git as the source of truth**. Each phase becomes its own subplan in this folder (`plans/git-native-kb/`).

This is the high-level roadmap. It is sequenced. Companion diagrams live in [`00b-diagrams.md`](00b-diagrams.md). The design rationale + references live in the ADR: [`docs/adr/0001-git-native-knowledge-base.md`](../../docs/adr/0001-git-native-knowledge-base.md).

> **SCOPE:** BACKEND only (`surfsense_backend`). Frontend (`surfsense_web`), the real-time UI (Zero), and client apps (desktop, Obsidian, browser extension) are touched only where a phase forces it (Phase 6). A dedicated frontend/client umbrella comes LATER, once the backend is working.

> **Origin:** Rohan Verma's meeting proposal to pivot from the custom-built KB "file system" to a Git-based system due to persistent maintenance issues; Thierry Bakera to investigate. This umbrella is the outcome of that investigation.

## Positioning

The KB today has **no real filesystem** — it is a *virtual* `/documents/` namespace faked over Postgres rows, plus three hand-rolled versioning/audit systems. That re-implements — badly — what Git provides natively (tree, atomic commits, history, revert, content-addressed dedup). The pivot makes **Git the single source of truth for all indexed content** and demotes **Postgres to a derived, rebuildable search index (chunks + embeddings only)**. Net effect: large code **deletion**, storage and search **decoupled** (so search can improve independently — Rohan's stated goal), and a real git repo per workspace (unlocking "bring your own remote" later).

## Target architecture (git = truth, Postgres = derived index)

```mermaid
flowchart TD
  subgraph WRITE["Write path (one path for everything indexed)"]
    AG["Agent notes"] --> GIT
    ED["Editor saves (Plate.js)"] --> GIT
    UP["Uploads (extracted markdown)"] --> GIT
    NOT["Indexable connectors: Notion / Drive / Obsidian"] --> GIT
  end
  GIT["Git repo per workspace (SOURCE OF TRUTH)\ncommit per turn/save · dulwich · per-workspace lock"]
  GIT --> IDX["Indexer: diff tree → changed blobs\n(embed keyed by blob SHA)"]
  IDX --> PG[("Postgres = DERIVED index\nchunks + embeddings only (rebuildable)")]
  subgraph READ["Agent"]
    FS["file ops: ls/read/write/edit/mv/rm"] --> GIT
    SR["semantic search"] --> PG
  end
  LIVE["Live connectors: Slack / Gmail"] -.->|queried at chat time, never stored| SKIP["(bypass storage entirely)"]
  BLOB[("Blob store / Azure — original binaries (unchanged)")]
```

<details>
<summary>Current (to-be-replaced) architecture — virtual FS over Postgres</summary>

```mermaid
flowchart TD
  AG["Agent tools ls/read/write/edit/mv/rm"] --> KBP["KBPostgresBackend (fakes files over rows)"]
  KBP --> PR["path_resolver.py (computes fake /documents/ paths)"]
  AG --> MW["kb_persistence middleware (commit-at-end-of-turn → Postgres)"]
  MW --> DOCS[("documents + folders + chunks")]
  MW --> V1["DocumentVersion"]
  MW --> V2["DocumentRevision / FolderRevision + revert_service"]
  MW --> V3["AgentActionLog"]
```

</details>

## Decisions locked

- **Git = single source of truth** for all *indexed* KB content (agent/editor notes, uploads, indexable connectors — the `is_indexable` ones).
- **Postgres = derived index only** (chunks + embeddings). It is a **cache**: wipe-and-rebuild from Git via one `reindex(workspace)`. Never authoritative.
- **One-way derivation** (Git → Postgres). **Never** two-way sync (this is the Wiki.js anti-pattern we explicitly reject).
- **Live connectors (Slack/Gmail) are untouched** — never stored/indexed, queried at chat time; entirely out of scope.
- **Binary blobs stay in the existing blob store** (local/Azure). Git holds extracted markdown, not raw binaries (Git-LFS deferred).
- **Agent tool interface is unchanged** (`ls/read/write/edit/mv/rm`). Only the backend behind the tools changes (Postgres-fake → real git working tree).
- **History/undo = git log + `git revert`.** The three hand-rolled systems (`DocumentVersion`, `DocumentRevision`/`FolderRevision`+`revert_service`) are **deleted**.
- **Engine = dulwich** (pure Python, deploy-friendly in Docker, real wire protocol for future remotes). Shell out to `git` only for heavy maintenance (`gc`/repack).
- **Per-workspace write lock** is mandatory (git is single-writer) — a data-integrity boundary, not a feature.
- **Rollout behind a feature flag**, per-workspace; no big-bang cutover.
- **Ports & Adapters shape** ([ADR 0002](../../docs/adr/0002-knowledge-core-ports-and-adapters.md)): the KB is a framework-agnostic **core** (`KnowledgeStore`); deepagents is one **adapter**, not the core. See "Architecture shape" below.

## Architecture shape — Ports & Adapters (core + adapters)

The KB is a **framework-agnostic core** (`KnowledgeStore`) surrounded by adapters. deepagents is **one driving adapter**, not the core — because the same knowledge already has several consumers (chat agent, a KB REST API, the vector-store sync, later MCP / remote git). Coupling the core to deepagents would force every other consumer through an agent framework. Rationale + sources (Cockburn Hexagonal, git plumbing/porcelain, libgit2): [ADR 0002](../../docs/adr/0002-knowledge-core-ports-and-adapters.md).

```mermaid
flowchart LR
  subgraph ADAPTERS_IN["Driving adapters (world → core)"]
    DA["deepagents backend<br/>(Phase 2 — build now)"]
    API["KB REST API<br/>(deferred)"]
    MCP["MCP server<br/>(deferred)"]
  end
  CORE["KnowledgeStore<br/>(framework-agnostic core)"]
  ENGINE["VersionedContentEngine → GitContentEngine (dulwich)<br/>driven port — build now (Phase 1)"]
  SYNC["Vector-store sync / derived index<br/>driven consumer (Phase 4 — build now)"]
  REMOTE["Remote git (GitHub/GitLab)<br/>driven adapter (deferred)"]
  DA --> CORE
  API -.-> CORE
  MCP -.-> CORE
  CORE --> ENGINE
  CORE -->|commits| SYNC
  ENGINE -.-> REMOTE
```

| Role | Consumer | v1? |
|---|---|---|
| Driving adapter | deepagents agent backend | ✅ build now (Phase 2) |
| Driving adapter | KB REST API (Rohan's artifact API) | deferred — next adapter after the core |
| Driving adapter | MCP server | deferred |
| Driven port (infra) | storage engine (dulwich via `VersionedContentEngine`) | ✅ built (Phase 1) |
| Driven consumer | vector-store sync / derived index | ✅ build now (Phase 4) |
| Driven adapter | remote git (GitHub/GitLab) | deferred |

**YAGNI:** build only the **core + deepagents adapter + vector-store-sync consumer**. Shape the ports so REST/MCP/remote-git slot in later, but **do not build them now**. Grow the port surface on demand — capabilities (`ls`/`grep`/`glob`, version/diff verbs) live once in the core, and each adapter takes the subset it needs; no speculative methods, no per-consumer reimplementation.

## References we are borrowing from (not inventing)

Every decision traces to a proven source (full list + links in the ADR):

| Decision | Borrowed from |
|---|---|
| Git = truth, Postgres = rebuildable cache | **Fossil SCM** (`fossil rebuild`, production since 2007) |
| Content in git, metadata/index in a DB | **Gollum** (GitHub/GitLab wikis), **kherad** |
| Silent commit-per-save, hide git from users | **kherad** |
| Embeddings keyed by blob SHA, incremental | **Coregit** + vector-index-as-cache best practices (LangChain RecordManager / LlamaIndex docstore) |
| Python git engine | **dulwich** |
| "Don't put a firehose in git" | "Git is not a database" critiques (validates keeping live connectors out) |
| Reject two-way DB↔git sync | **Wiki.js** counter-example (requarks/wiki #7860 silent-sync bug) |

## Backend phases (active — this umbrella)

### Phase 0 — Shared contract [`subplan: 00c-shared-contract.md`]

> **READ FIRST.** Pins the five cross-phase contracts (repo/tree layout, read contract + citation model, lock, write path, index/Zero realities) grounded in the current code. Resolves what were per-phase "open questions". Two contracts were revised on 2026-07-28 after the adapter brainstorm: reads are **raw from the per-turn worktree** with one line-anchored citation pattern (C2), and in-turn writes live in a **per-turn worktree**, not the state overlay (C6).

### Phase 1 — Knowledge store core [`subplan: 01-git-storage-core.md`] ✅ implemented

> **DONE. Built first** — every later phase uses it.

- Added **dulwich**; a `KnowledgeStore` facade that opens/creates a **persistent working tree per workspace** on disk, nested under the shared blob-store volume (`{FILE_STORAGE_LOCAL_PATH}/knowledge_store/{workspace_id}`). Git lives behind the facade (`engines/git.py`).
- API (SQL-transaction vocabulary, no git words; capabilities are verbs): `transaction(message, author)` scope yielding a `Transaction` with `write`/`remove`/`move` that records one atomic revision on clean exit; `read_as_of`, `list_revisions`, `list_changes`, `list_paths`, `get_current_revision`, `compute_content_id`. First use bootstraps the store — no init ceremony. Snapshot/batch is an engine detail. (Structure primitives, if any prove needed → Phase 2; undo/forward-restore → Phase 4.)
- **Per-workspace Redis write lock** around commits (single-writer safety across all OS processes). `ponytail:` lock ceiling = one lock per commit; upgrade path = queue/worker.
- Key files (new): `surfsense_backend/app/knowledge_store/` (`store`, `transaction`, `write_lock`, `store_path`, `settings`, `engines/{base,git}`). No agent wiring yet.
- Tests — unit (`tests/unit/knowledge_store/`): engine behavior on temp repos, pure `Transaction` logic; integration (`tests/integration/knowledge_store/`, real Redis): write-lock semantics and the facade `transaction` end to end.

### Phase 2 — deepagents adapter over the core [`subplan: 02-git-working-tree-backend.md`]

> **SHIPPED (file-op path, 2026-07-28).** The **first driving adapter** ([ADR 0002](../../docs/adr/0002-knowledge-core-ports-and-adapters.md)) — deepagents talking to the core over the real git working tree, replacing the read-side fake. Remaining in-phase: the C2 `read_file` citation envelope (after Phase 4's line spans, so search and read citations land as one model).

- `GitTreeBackend` serves `/documents/...` from the turn's **private working copy** (lazy open on the first KB tool call; copy id = `thread-{thread_id}`), implemented as one `MultiRootLocalFolderBackend` mount — no staging, no state overlay.
- Working-copy lifecycle (`open`/`diff`/`discard`/`prune`) lives in the core behind the port; wired into `resolver.py` behind `KNOWLEDGE_STORE_ENABLED`; mutation tools route down the direct-op branches.
- `path_resolver` + `KBPostgresBackend` retire for flagged workspaces (deleted at the Phase 5 cut).
- Tests: lifecycle on temp repos, adapter behavior on real files, resolver gating.

### Phase 3 — Commit-per-turn write path [`subplan: 03-commit-write-path.md`]

> **SHIPPED (2026-07-29).** See the subplan's work items for the small as-built deviations.

- Persistence middleware `knowledge_store_persistence/` alongside `kb_persistence` (untouched until Phase 5 cut): end of turn → diff the working copy → one `transaction` → receipts → discard. Free-function commit body; the disconnect fallback in `event_loop.py` runs the identical routine (no state markers — the copy on disk is the pending state).
- Model-generated commit subjects with deterministic fallback (`Thread:` trailer); the model seam is wired with the agent LLM until a weak-model role exists. Honest attribution: author = user, committer = agent (`knowledge_store/identities.py`).
- Receipts created post-commit from `list_changes(revision)`, revision id as `external_id`; commit failure returns `failed` receipts and keeps the copy for next-turn recovery. Zero events move with Phase 4/6.
- Editor saves and upload-extracted markdown route through `document_revision_recorder` (same single write path); connector-indexable sync still pending. Daily Celery beat janitor prunes abandoned copies.
- Tests shipped: commit-turn scenarios against real git + Redis (net changes, no-op turns, contention recovery), message fallback, builder gating, recorder, janitor TTL.

### Phase 4 — Derived index + reindex [`subplan: 04-derived-index.md`]

> **PLANNED. Can build alongside 03** (both consume 01's `transaction`/`list_changes`). This is the **vector-store-sync driven consumer** ([ADR 0002](../../docs/adr/0002-knowledge-core-ports-and-adapters.md)): it subscribes to revisions one-way; the core has no knowledge of it.

- Post-revision indexer: `list_changes(revision)` names the changed paths; re-chunk + re-embed **only those**, keying embeddings by **content id** so unchanged content reuses its vectors. Store each chunk's line span at cut time (C2 rendering). `web`/live paths untouched.
- One idempotent **`reindex(workspace)`** that wipes and rebuilds all chunks/embeddings from the current revision (the Fossil `rebuild` discipline), as a Celery task.
- The three hand-rolled versioning systems become dead code for flagged workspaces; their **deletion (code + table drops) is Phase 5 cut time**.
- Tests: change one file → only its chunks re-embed (unchanged blob SHAs reuse vectors); `reindex()` reproduces identical chunk set; search results unchanged vs. baseline.

### Phase 5 — Migration [`subplan: 05-migration.md`]

> **PLANNED. After 01–04.** One-time, per-workspace, flagged.

- Export each existing workspace's Postgres documents/folders → an initial git repo (one seed commit), preserving `unique_identifier_hash` mapping.
- Verify round-trip: seeded repo → `reindex()` → chunk set matches pre-migration search behavior.
- Rollback = keep Postgres content until the flagged workspace is verified.

### Phase 6 — Zero / real-time projection [`subplan: 06-zero-projection.md`]

> **PLANNED. The one net-new integration cost.** Depends on 03/04.

- The web UI is driven by Zero (Postgres logical replication, `zero_publication.py`). Git is not a real-time source, so add a **git → Postgres projection** that keeps the Zero-published `documents`/`folders` rows in sync after each commit (thin metadata rows, not content-authoritative).
- Decide: reuse the indexer's post-commit hook to upsert Zero rows vs. a separate projector.
- Tests: after a commit, the Zero-published rows reflect the new tree within the projection cycle; deleting a file removes its row.

## Sequencing (critical path vs. parallel)

- **Phase 0 first:** `00c` is a design agreement (no code) — sign off on the five contracts before starting `01`.
- **Critical path:** `01 → 02 → 03` (storage → backend → write path). These deliver the core swap.
- **Parallelizable:** `04` (indexer/reindex) can develop alongside `03`; both only need `01`'s `commit`/`log`.
- **After core:** `05` (migration) then `06` (Zero projection). `06` is the only genuinely *new* subsystem (partly offsets the deletions) and must land before flagging a workspace whose UI must stay live.
- Recommended: `01 → 02 → 03` (+`04` in parallel) → `06` → `05` → flip flag per workspace.

## Deferred — out of this umbrella

- **Connect-your-own-remote** (push/pull to user GitHub/GitLab/Gitea). Free later because the repo is real git.
- **CRDT / Yjs real-time collaboration** (multi-writer). Keep single-writer for now.
- **Review / merge workflows** (kherad's reviewer layer).
- **Karpathy `raw/` + `wiki/` content model, contradiction-flagging, lint.**
- **Graphiti / bi-temporal fact graph** (agent memory time-travel).
- **Git-LFS for binaries** (blob store stays).
- **Frontend/client umbrella** (version-history UI removal, any UX changes).

## Open items — resolved in Phase 0 ([`00c-shared-contract.md`](00c-shared-contract.md))

1. ~~Repo location & layout~~ → **persistent working tree at `{FILE_STORAGE_LOCAL_PATH}/knowledge_store/{workspace_id}`, layout = virtual path minus `/documents`** (C1).
2. ~~Zero projection owner~~ → **folded into the Phase-4 post-commit indexer** (C5).
3. **Binaries** — keep blob store (confirmed markdown/text-only in git); Git-LFS deferred.
4. ~~Lock granularity~~ → **Redis lock, from v1** (deploy is multi-process: uvicorn + Celery) (C3).
5. ~~`content_hash` vs blob SHA~~ → **different values (content_hash is workspace-salted); key reuse by blob SHA, keep content_hash through migration** (C5).
6. **Migration cutover** — per-workspace flag flip after parity check; rollback = keep Postgres content until verified (Phase 5).

Still genuinely open (non-blocking): commit-message format, `gc`/repack scheduling, `reindex` observability.

## Resolved decisions log

- **(2026-07-24) PIVOT ADOPTED — Git as source of truth, Postgres as derived index.** Outcome of the KB maintenance investigation (ADR 0001). Git owns all *indexed* content; Postgres holds only chunks+embeddings and is rebuildable via `reindex()`. One-way derivation only (git→Postgres); two-way sync explicitly rejected (Wiki.js #7860). Live connectors (Slack/Gmail) unchanged and out of scope. Agent tool interface unchanged; only the backend behind it swaps. Three hand-rolled versioning systems to be deleted in favor of git history/`revert`. Engine = dulwich. Rollout behind a per-workspace feature flag.
- **(2026-07-24) Connectors clarified — only `is_indexable` content enters git.** Document connectors (Notion, Drive, Obsidian) are indexed → they go into git. Live connectors (Slack, Gmail) are queried at chat time and never stored → they never touch git or Postgres chunks. (Corrects an earlier draft that carved *all* connectors out of git.)
- **(2026-07-24) Borrowing, not inventing.** Architecture assembled from proven references (Fossil, Gollum, kherad, Coregit, dulwich, vector-cache best-practices); the only SurfSense-specific work is the adaptation glue. Wiki.js retained as the explicit counter-example.
- **(2026-07-28) Ports & Adapters — deepagents is an adapter, not the core** ([ADR 0002](../../docs/adr/0002-knowledge-core-ports-and-adapters.md)). The KB is a framework-agnostic core (`KnowledgeStore`); consumers (deepagents, the KB REST API, the vector-store sync, later MCP/remote-git) are adapters at the edge. **YAGNI:** v1 builds only the core + the deepagents adapter (Phase 2) + the vector-store-sync consumer (Phase 4); REST/MCP/remote-git are named-but-deferred. Ports grow on demand. Borrowed from Cockburn (Hexagonal), git plumbing/porcelain, libgit2.

## Subplan index (backend)

| Phase | Subplan file | Status |
|-------|--------------|--------|
| 0 | `00c-shared-contract.md` | PLANNED — read first |
| 1 | `01-git-storage-core.md` (core) | ✅ implemented |
| 2 | `02-git-working-tree-backend.md` (deepagents adapter) | PLANNED |
| 3 | `03-commit-write-path.md` | PLANNED |
| 4 | `04-derived-index.md` | PLANNED |
| 5 | `05-migration.md` | PLANNED |
| 6 | `06-zero-projection.md` | PLANNED |
| — | `00b-diagrams.md` | companion flow diagrams |

Frontend & client subplans will be added under a separate umbrella later (see "Deferred").

## Appendix — current implementation file index (what each phase touches)

| Topic | Path |
|---|---|
| Virtual path resolver (retire) | `surfsense_backend/app/agents/chat/runtime/path_resolver.py` |
| Virtual FS read backend (replace) | `.../filesystem/backends/kb_postgres.py` |
| Backend resolver (rewire) | `.../filesystem/backends/resolver.py` |
| Write commit middleware (repoint) | `.../main_agent/middleware/kb_persistence/middleware.py` |
| Hybrid search (unchanged) | `.../shared/retrieval/hybrid_search.py` |
| Chunk reconciliation (key by blob SHA) | `surfsense_backend/app/indexing_pipeline/chunk_reconciler.py` |
| Indexing pipeline | `surfsense_backend/app/indexing_pipeline/indexing_pipeline_service.py` |
| User version history (delete) | `surfsense_backend/app/utils/document_versioning.py` |
| Agent revert (delete) | `surfsense_backend/app/services/revert_service.py` |
| Zero publication (project into) | `surfsense_backend/app/zero_publication.py` |
| ORM models | `surfsense_backend/app/db.py` |
