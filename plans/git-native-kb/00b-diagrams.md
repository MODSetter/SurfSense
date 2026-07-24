# Git-native KB — flow diagrams (end-to-end)

> Visual companion to [`00-umbrella-plan.md`](00-umbrella-plan.md).
> Phase refs: `01` storage core · `02` working-tree backend · `03` commit write path · `04` derived index · `05` migration · `06` Zero projection.

## 1. The shape — one source of truth, one derived index

```mermaid
flowchart LR
  subgraph TRUTH["SOURCE OF TRUTH"]
    GIT["Git repo per workspace\n(commit per turn/save)"]
  end
  subgraph DERIVED["DERIVED (rebuildable cache)"]
    PG[("Postgres: chunks + embeddings")]
  end
  GIT -->|"one-way derivation (04)"| PG
  PG -. "reindex(workspace) rebuilds from git (04)" .-> GIT
  classDef t fill:#1f3a2e,stroke:#4f9d76,color:#e6f7ee;
  classDef d fill:#22314f,stroke:#5b7fbf,color:#e6edf7;
  class GIT t;
  class PG d;
```

There is **no arrow from Postgres back into Git**. Postgres is disposable.

## 2. Write path — everything indexed becomes a commit

```mermaid
flowchart TD
  AG["Agent edits (turn)"] --> WT["Working tree (staged)"]
  ED["Editor save"] --> WT
  UP["Upload → extracted markdown"] --> WT
  NOT["Indexable connector sync (Notion/Drive)"] --> WT
  WT -->|"end of turn / save (03)"| C["git commit (per-workspace lock, 01)"]
  C --> IDX["Indexer: diff tree → changed blobs (04)"]
  IDX --> PG[("chunks + embeddings\n(embed keyed by blob SHA)")]
  C --> ZP["Zero projection: upsert documents/folders rows (06)"]
```

## 3. Read path — file ops vs. search hit different stores

```mermaid
flowchart LR
  A["Agent"] -->|"ls/read/write/edit/mv/rm"| B["Git working-tree backend (02)"]
  B --> GIT["Git (truth)"]
  A -->|"semantic search"| S["hybrid_search (unchanged)"]
  S --> PG[("Postgres chunks + embeddings")]
```

## 4. Live connectors — never stored (out of scope)

```mermaid
flowchart LR
  Q["Chat query"] --> LC["Slack / Gmail (live)"]
  LC -->|"fetched at chat time"| ANS["used in the answer"]
  LC -.->|"never"| GIT["Git"]
  LC -.->|"never"| PG[("Postgres chunks")]
```

## 5. History / undo — git replaces the three hand-rolled systems

```mermaid
flowchart TD
  subgraph OLD["BEFORE (deleted)"]
    V1["DocumentVersion"]
    V2["DocumentRevision / FolderRevision + revert_service"]
    V3["AgentActionLog (audit)"]
  end
  subgraph NEW["AFTER"]
    L["git log / diff (history)"]
    R["git revert (undo)"]
    BL["git blame (attribution)"]
  end
  OLD -->|"replaced by (04)"| NEW
```

## 6. Migration (05) — Postgres KB → seed git repo

```mermaid
sequenceDiagram
  autonumber
  participant M as Migrator (per workspace, flagged)
  participant PG as Postgres (existing docs/folders)
  participant GIT as New git repo
  participant IDX as reindex(workspace)
  M->>PG: read documents + folders (preserve unique_identifier_hash)
  M->>GIT: write files + one seed commit
  M->>IDX: rebuild chunks/embeddings from git HEAD
  IDX-->>M: chunk set
  M->>M: verify search parity vs pre-migration, then flip flag
  Note over M,GIT: Postgres content kept until verified (rollback window).
```

## 7. Reindex (04) — the safety net (Fossil `rebuild`)

```mermaid
flowchart LR
  GIT["Git HEAD (truth)"] --> RB["reindex(workspace)"]
  RB --> WIPE["wipe chunks + embeddings"]
  WIPE --> REBUILD["re-chunk + re-embed all files\n(reuse cache by blob SHA)"]
  REBUILD --> PG[("Postgres index rebuilt")]
```
