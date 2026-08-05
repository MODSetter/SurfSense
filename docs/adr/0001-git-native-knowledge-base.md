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

---

## We are borrowing from authoritative sources, not inventing

Every decision traces to a proven, battle-tested reference. The only SurfSense-specific work is the *adaptation glue*.

| Decision | Borrowed from |
|---|---|
| Git = truth, Postgres = rebuildable cache | **Fossil SCM** — canonical artifacts + SQL tables as a pure cache, recomputed via `fossil rebuild` (production since 2007). https://fossil-scm.org/home/doc/trunk/www/theory1.wiki |
| Content in git, metadata/index in a DB | **Gollum** (GitHub/GitLab wikis): "storage abstraction layer... only some data in the DB". https://github.com/gollum/gollum · https://docs.gitlab.com/17.5/development/wikis/ |
| Silent commit-per-save, hide git from users | **kherad**. https://github.com/mohammadmaso/kherad |
| Embeddings keyed by blob SHA, incremental (not rebuild) | **Coregit LLM Wiki** (https://coregit.dev/blog/llm-wiki-launch) + vector-index-as-cache best practices (LangChain RecordManager, LlamaIndex docstore). Cache key = `(model_version, content_hash)`. |
| Python git engine | **dulwich** — pure Python, deploy-friendly, real wire protocol. https://github.com/jelmer/dulwich |
| "Don't put a firehose in git" / git limits | "Git is not a database" critiques — degrades past ~500k–1M files, no query engine, no concurrency control. |
| Future content model (`raw/`+`wiki/`, lint, contradiction-flagging) | **Karpathy's LLM Wiki**. https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f |
| Future real-time collab | **Yjs** (Notion, Linear). https://github.com/yjs/yjs |
| Future fact-level temporal memory | **Zep / Graphiti** (bi-temporal, "invalidate don't delete"). https://arxiv.org/html/2501.13956 |

### The counter-example we explicitly reject

**Wiki.js** git module = DB is truth, git is a two-way mirror. This creates two sources of truth and a reconciliation cursor; it has a known class of silent-sync bugs (see requarks/wiki discussion #7860). We use **one-way derivation** (git → Postgres), never two-way sync.

---

## Scope: v1 (keep it simple)

Ship the smallest thing that removes the maintenance pain:

1. **Git repo per workspace** (dulwich) holding indexed content as markdown.
2. **One commit per agent turn / editor save.** No branches, no merge, no review workflow.
3. **Delete** the three versioning systems; history/undo = git log + `git revert`.
4. **pgvector stays**, rebuilt from git, keyed by blob SHA (point existing `chunk_reconciler` at blob SHA so unchanged files skip re-embedding).
5. **Per-workspace lock/queue** around commits (git is single-writer; this is a data-integrity boundary, not a feature — non-negotiable).
6. **One `reindex(workspace)` function** that wipes and rebuilds Postgres chunks from the git repo (the Fossil `rebuild` discipline — makes the system safe to ship early).

### Deferred (v2+, explicitly out of v1)

- Connect-your-own-remote (GitHub/GitLab) — free later because the repo is real git.
- CRDT / Yjs real-time collaboration.
- Review / merge workflows (kherad's reviewer layer).
- Graphiti / bi-temporal fact graph.
- Karpathy `raw/` + `wiki/` content model, contradiction-flagging, lint.

---

## Consequences

### Positive

- Large net **deletion** of bespoke code (the maintenance win).
- Storage and search **decouple** → the team can improve semantic search independently (Rohan's stated goal).
- Postgres becomes disposable/rebuildable → simpler recovery, fewer consistency bugs.
- Unlocks future "user owns their KB as a real git repo" differentiator.

### Negative / risks

- **Concurrency:** git is single-writer per repo → requires the per-workspace lock (mitigated in v1).
- **Repo hygiene:** many small commits → periodic `git gc`/repack (operational, manageable).
- **Migration:** existing Postgres KBs must be exported into git repos once, preserving `unique_identifier_hash` mapping.
- **Real-time UI (Zero):** currently driven by Postgres logical replication; still needs a git → Postgres projection to keep the web client live. This is *new* code that partially offsets deletions.

---

## Open questions (for team discussion)

1. **Zero / real-time UI:** confirm the git → Postgres projection path and whether Zero stays as-is.
2. **Binaries:** keep blob store vs. adopt Git-LFS.
3. **Migration cutover:** big-bang vs. per-workspace feature flag (recommend feature-flag rollout).
4. **Merge UX later:** CRDT (Yjs) vs. review-gate (kherad) when multi-writer becomes a requirement.

---

## Appendix: key file index (current implementation)

| Topic | Path |
|---|---|
| Virtual path resolver | `surfsense_backend/app/agents/chat/runtime/path_resolver.py` |
| Virtual FS read backend | `.../filesystem/backends/kb_postgres.py` |
| Virtual FS write commit | `.../main_agent/middleware/kb_persistence/middleware.py` |
| Hybrid search | `.../shared/retrieval/hybrid_search.py` |
| Chunk reconciliation | `surfsense_backend/app/indexing_pipeline/chunk_reconciler.py` |
| User version history | `surfsense_backend/app/utils/document_versioning.py` |
| Agent revert | `surfsense_backend/app/services/revert_service.py` |
| ORM models | `surfsense_backend/app/db.py` |
