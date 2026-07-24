# ADR 0001: Git-native Knowledge Base (Git as source of truth, Postgres as derived index)

- **Status:** Proposed (brainstorm outcome — for team review)
- **Date:** 2026-07-24
- **Origin:** Rohan Verma's meeting proposal to pivot from the custom-built KB "file system" to a Git-based system due to persistent maintenance issues; Thierry Bakera to investigate.

---

## Context

### What we have today

SurfSense does **not** actually have a file system. It has a **virtual filesystem façade mapped onto Postgres rows**, used by the chat agent. The moving parts:

- Virtual `/documents/` namespace computed from DB rows — `surfsense_backend/app/agents/chat/runtime/path_resolver.py`
- Read-side backend faking `ls`/`read`/`glob`/`grep` over Postgres — `.../filesystem/backends/kb_postgres.py`
- Write-side "commit at end of turn" layer — `.../main_agent/middleware/kb_persistence/middleware.py`
- **Three separate hand-rolled versioning/audit systems:**
  - `DocumentVersion` (user history) — `app/utils/document_versioning.py`
  - `DocumentRevision` / `FolderRevision` (agent revert snapshots) — `app/services/revert_service.py`
  - `AgentActionLog` (tool-call audit)
- Supporting machinery: fractional indexing for ordering, move tracking, `content_hash` change detection, chunk reconciliation.

### The problem

The team has been hand-implementing — on top of a relational DB never designed for it — the exact primitives Git provides natively. That re-implementation is the source of the "persistent maintenance issues."

| Hand-rolled today | Git provides natively |
|---|---|
| `path_resolver` + folder tree | tree objects |
| end-of-turn staged commit | atomic commits |
| `DocumentVersion` snapshots | commit history |
| `DocumentRevision` + `revert_service` | `git revert` / `reset` |
| `AgentActionLog` | commit log / `blame` |
| `content_hash` dedup | content-addressed blobs (SHA) |
| fractional indexing / move tracking | tree diff / rename detection |

### Search stack (unchanged by this ADR)

Hybrid chunk search: pgvector (HNSW) + Postgres FTS + RRF, optional reranking. Chunking via Chonkie; incremental via `chunk_reconciler.py`. See `.../shared/retrieval/hybrid_search.py`.

---

## Decision

**Adopt Git as the single source of truth for all indexed KB content. Postgres becomes a derived, rebuildable index holding only chunks + embeddings.**

### Core model

```
agent notes ─┐
editor saves ─┤
uploads ──────┤→  Git commit (source of truth)  →  indexer  →  Postgres (chunks + embeddings)
Notion ───────┤
Drive ────────┘
(indexable connectors only)

Slack / Gmail (live connectors) ──→ queried at chat time, bypass storage entirely
```

- **Git = truth** for everything that gets stored/indexed (agent/editor notes, uploads, and **indexable** connectors like Notion, Drive, Obsidian — the `is_indexable` connectors).
- **Postgres = derived index only** (chunks + embeddings). It is a **cache**: it can be wiped and rebuilt from Git at any time via a single `reindex(workspace)` function.
- **Live connectors (Slack, Gmail)** are never stored or indexed — they are queried live at chat time and are entirely out of scope for this design.
- **Binary blobs** (original PDF/DOCX) stay in the existing local/Azure blob store (or Git-LFS later); Git holds the extracted markdown, not raw binaries.

### What changes for the agent

The agent's **tools are unchanged** (`ls`, `read`, `write`, `edit`, `mv`, `rm`). Only the backend behind them changes:

| Agent action | Backed by |
|---|---|
| File ops (`ls`/`read`/`write`/`edit`/`mv`/`rm`) | **Git** working tree (real files) |
| Semantic search | **Postgres** (derived chunk/embedding index) |

- **Before:** `KBPostgresBackend` fakes files over Postgres rows.
- **After:** a Git-working-tree backend operates on **real files**. `path_resolver` largely disappears (paths are real).
- **Write flow:** agent edits → git working tree → **one commit at end of turn** (replaces the `kb_persistence` commit-to-Postgres step) → indexer refreshes Postgres chunks.

### What we delete

- The virtual-FS façade (`path_resolver`, `kb_postgres` staging).
- `DocumentVersion`, `DocumentRevision` / `FolderRevision`, `revert_service` → replaced by git history + `git revert`.
- Fractional indexing / bespoke move tracking → git tree operations.

This pivot is **mostly deletion**, which is the point.
