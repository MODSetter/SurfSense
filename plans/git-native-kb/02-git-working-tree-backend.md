# Phase 2 — deepagents adapter over the core

> Build after Phase 1. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md). Shape: [ADR 0002](../../docs/adr/0002-knowledge-core-ports-and-adapters.md).
> The **first driving adapter**: deepagents talking to the framework-agnostic core (`KnowledgeStore`) over the **real git working tree**, replacing the read-side fake (`KBPostgresBackend`). Agent tools are unchanged.

## Objective

Give the agent `ls/glob/grep`/structure from the **real git tree** instead of `path_resolver` + a DB folder walk — as a **thin deepagents adapter**, not a bespoke filesystem reimplementation. The adapter reuses deepagents' own `FilesystemBackend`/git plumbing for read-only structure and routes writes + commit through the core, so the write lock, commit policy, and citation policy have one home.

## Locked model

- **This is an adapter, not the core.** The core (`KnowledgeStore`) stays framework-agnostic (imports no deepagents). Only this file knows about `BackendProtocol`. Capabilities live in the core; the adapter selects the subset the agent needs and adds no storage logic of its own.
- **Reuse deepagents' built-ins; don't reimplement the framework.** deepagents already ships a `FilesystemBackend` (direct-disk) and `CompositeBackend` (prefix routing). Point them at the workspace git working tree for read-only structure (`als_info`/`aglob_info`/`agrep_raw`/`alist_tree_listing`) rather than hand-rolling scans. Only writes + commit are custom, because they must go through the core's lock/commit path.
- **Same tool interface.** The adapter satisfies the exact `BackendProtocol` surface the agent expects (`als_info`, `aread`, `awrite`, `aedit`, `aglob_info`, `agrep_raw`, `alist_tree_listing`), returning the upstream `WriteResult`/`EditResult`/`FileInfo`/`GrepMatch` shapes — no extra fields.
- **`path_resolver` path computation retires for flagged workspaces** — folder walk + collision suffixing → real repo paths (filename rules still reused, C1). Keep `DOCUMENTS_ROOT` as the repo-relative prefix for continuity.
- Selected via the resolver behind `KNOWLEDGE_STORE_ENABLED`.

## Open — decide within this phase

C2/C6 assumed the current Postgres backend's behavior; both are reopened here. Pick the simplest option that works.

- **`read_file` citation model.** (a) chunk-render (`aload_document`/`render_full_document`, C2) so `[n]` doesn't regress, or (b) raw git blob with per-document citations. Current citations are poor (Rohan) — choose on citation quality, not on preserving today's path.
- **In-turn write visibility / turn isolation.** Reuse the `runtime.state` overlay (`_pending_filesystem_view`, C6), or write to the tree directly (`FilesystemBackend`) with a per-turn boundary (per-workspace lock vs per-turn worktree). Confirm the overlay is still needed before porting it.

## Work items

1. Add only the read-side core primitives the adapter actually needs and that deepagents' backends can't already serve (e.g. a repo-relative `list_tree(prefix)` if `FilesystemBackend` listing isn't a clean fit). Grow the port on demand — no speculative methods.
2. New `.../filesystem/backends/git_tree.py` — the deepagents adapter: compose deepagents' `FilesystemBackend` (pointed at the workspace tree) for structure, and route `awrite`/`aedit` through `KnowledgeStore` for the eventual commit (Phase 3).
3. Wire into `.../filesystem/backends/resolver.py::build_backend_resolver`: when `KNOWLEDGE_STORE_ENABLED` and `workspace_id is not None`, return the git-tree adapter instead of `KBPostgresBackend`.
4. Gate `path_resolver`/`kb_postgres` usage behind the flag (keep both paths compilable during rollout).

## Tests

- For a seeded repo, `ls`/`glob`/`grep`/`list_tree` return results **identical** to `KBPostgresBackend` for the same content (golden comparison).
- `read_file` of a nested path returns the resolved document; **if** v1 keeps chunk-render, it registers the same `[n]` citations as the Postgres backend (contingent on the citation decision above).
- Resolver returns the git-tree adapter only when the flag is on; falls back to `KBPostgresBackend`/`StateBackend` otherwise.

## Out of scope

- End-of-turn commit → Phase 3. Index refresh (vector-store-sync consumer) → Phase 4.
- Desktop-local (`MultiRootLocalFolderBackend`) path — unchanged.
- Other adapters (KB REST API, MCP) — deferred (ADR 0002, YAGNI).
