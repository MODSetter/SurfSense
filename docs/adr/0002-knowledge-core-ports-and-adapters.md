# ADR 0002: Knowledge core as Ports & Adapters (deepagents is an adapter, not the core)

- **Status:** Proposed (brainstorm outcome — for team review)
- **Date:** 2026-07-28
- **Relates to:** [ADR 0001](0001-git-native-knowledge-base.md) decides *what* the store is (git as source of truth, Postgres derived). This ADR decides the *shape* of the code around it.

---

## Context

Should the git-backed store be built **as a deepagents backend**, or as a **standalone core** that deepagents consumes?

The same knowledge already has **multiple real consumers**:

- the chat agent (deepagents filesystem tools),
- a **Knowledge Base REST API** (Rohan's mandate to standardize artifact generation and drop redundant UI dialogues),
- the **vector-store sync** (the derived chunk/embedding index),
- and, later, an **MCP server** and **connect-your-own-remote** (GitHub/GitLab).

If the core were a deepagents backend, every other consumer would have to route through an agent framework to touch the KB. That is the wrong dependency direction.

## Decision

**Structure the KB as Hexagonal / Ports & Adapters.** A framework-agnostic **knowledge core** exposes capabilities through **ports**; every consumer is an **adapter** at the edge; the core imports no consumer framework.

- **Core (inside the hexagon):** `KnowledgeStore` — versioned knowledge (content + history). Already framework-free (imports no deepagents).
- **Driven port** (core → infrastructure): `VersionedContentEngine` → `GitContentEngine` (dulwich). Swappable, mirroring libgit2's pluggable backends.
- **Driven consumer** (downstream of commits): the **vector-store sync / derived index** — subscribes to commits, one-way (git → Postgres). The core does not know it exists.
- **Driving adapters** (world → core): the **deepagents backend** (build now), the **KB REST API** (later), **MCP / remote git** (future). The core is oblivious to all of them.
- **Capabilities live once in the core; each adapter selects the subset it needs.** `ls`/`grep`/`glob` are offered for filesystem-shaped consumers (agent, MCP); document/version/diff verbs serve the REST API; commit-diff serves the sync. We never force one consumer's verbs on another, and never reimplement a capability per consumer.

## Borrowing, not inventing

| Element | Borrowed from |
|---|---|
| Framework-agnostic core, many adapters per port | **Cockburn — Ports & Adapters (Hexagonal)**: "there will typically be multiple adapters for any one port." https://alistair.cockburn.us/hexagonal-architecture |
| Agnostic core + thin consumer layer | **Git's own plumbing/porcelain split** — low-level toolkit as building blocks, user commands on top. https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain |
| Linkable core + pluggable storage backends for long-running services | **libgit2** (built precisely because forking the git binary is wrong for services) — same reasoning that chose **dulwich** behind `VersionedContentEngine`. |

## Scope — YAGNI (v1)

**Build now:** the **core** + the **deepagents adapter** + the **vector-store-sync driven consumer**. Nothing else.

- Design the ports so the **REST API** and **MCP/remote-git** adapters slot in later — but **do not build them now**.
- **Grow the port surface on demand:** add a capability when an adapter needs it. No speculative methods.
- The deepagents adapter should **reuse deepagents' own `FilesystemBackend`/git plumbing** for read-only structure ops (`ls`/`glob`/`grep`) rather than reimplementing them; writes + commit route through the core so the write lock, commit policy, and citation control have one home.

## Consequences

### Positive

- Consumers are decoupled: the KB REST API and MCP become **thin adapters**, not parallel rewrites of the KB.
- The core is testable with no agent framework in the loop; deepagents itself becomes swappable.
- Matches ADR 0001's "separate file management from the vector store/search" — the sync is just one driven consumer.

### Negative / cost

- One indirection (an adapter) over using `FilesystemBackend` directly — accepted because the consumers are real, not hypothetical (the YAGNI test for hexagonal).

## Open (deferred to their phases)

- **Citation model** for `read_file`: raw file vs chunk-rendered `[n]`. Rohan flagged current citations as poor — redesign candidate.
- **Commit granularity**: per-turn (Aider-style) vs per-mutation.
- **Turn isolation**: shared working tree + per-workspace lock vs per-turn worktree.
