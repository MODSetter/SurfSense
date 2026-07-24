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

