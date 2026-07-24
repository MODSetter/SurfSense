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
