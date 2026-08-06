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

## 2. The system — hexagon: agnostic core, one adapter per consumer

```mermaid
flowchart LR
  subgraph DRIVERS["Drivers (who mutates / reads content)"]
    AG["Agent (deepagents tools)"]
    ED["Editor / REST API"]
    CN["Indexable connector sync"]
  end
  subgraph ADAPTERS["Adapters (consumer-specific glue)"]
    GTB["deepagents adapter (02)\nserves file ops on the turn's\nprivate working copy"]
    DIR["direct callers (03)\none transaction per save/sync"]
  end
  subgraph CORE["Knowledge store — agnostic core"]
    KS["Facade\ntransaction · read_as_of · list_revisions\nlist_changes · list_paths · working copies"]
    ENG["Versioned content engine\n(git today; swappable behind the port)"]
  end
  subgraph DRIVEN["Driven consumers (react to new revisions)"]
    IDX["Vector-store sync (04)\nlist_changes → re-chunk / re-embed"]
    ZP["Zero projection (06)"]
  end
  AG --> GTB --> KS
  ED --> DIR --> KS
  CN --> DIR
  KS --> ENG
  KS -->|"new revision"| IDX
  KS -->|"new revision"| ZP
  classDef core fill:#1f3a2e,stroke:#4f9d76,color:#e6f7ee;
  classDef edge fill:#22314f,stroke:#5b7fbf,color:#e6edf7;
  class KS,ENG core;
  class AG,ED,CN,GTB,DIR,IDX,ZP edge;
```

Where each component lives (the code follows the dependency rule: the core
never knows its consumers, so adapters sit with their consumer):

| Component | Location |
| --- | --- |
| Facade, transaction, write lock, layout | `app/knowledge_store/` |
| Engine port + git engine | `app/knowledge_store/engines/` |
| deepagents adapter (`GitTreeBackend`) + resolver | `app/agents/.../middleware/filesystem/backends/` |
| End-of-turn commit middleware (03, pending) | `app/agents/.../middleware/` |

## 3. Turn lifecycle — git at the boundaries, plain files in between

Two locks, two different races:
**threading lock** (process-local, in `GitContentEngine`) serializes parallel tool
calls creating the same copy; **redis lock** (cross-process) serializes revision
recording against other workers.

```mermaid
sequenceDiagram
  autonumber
  participant T as Agent tool call
  participant A as GitTreeBackend (adapter)
  participant S as KnowledgeStore (facade)
  participant E as GitContentEngine (engine)
  T->>A: first KB op of the turn
  A->>S: open_working_copy("thread-{id}")
  S->>E: checkout current revision (threading lock)
  E-->>A: private copy path
  Note over T,A: rest of the turn: plain file ops on the copy\n(MultiRootLocalFolderBackend — no git involved)
  T->>A: end of turn (03, pending)
  A->>S: diff_working_copy → transaction
  S->>E: record one revision (redis write lock)
  S->>E: discard_working_copy
  Note over S,E: abandoned copies swept by janitor\n(prune_working_copies)
```

## 4. Write path — everything indexed becomes a commit

```mermaid
flowchart TD
  AG["Agent edits (turn)"] --> WC["Private working copy per thread (02)"]
  ED["Editor save"] --> TXD["KnowledgeStore.transaction"]
  UP["Upload → extracted markdown"] --> TXD
  NOT["Indexable connector sync (Notion/Drive)"] --> TXD
  WC -->|"end of turn: diff → transaction (03)"| TXD
  TXD --> C["one revision recorded\n(redis write lock, 01)"]
  C --> IDX["Indexer: list_changes → changed blobs (04)"]
  IDX --> PG[("chunks + embeddings\n(embed keyed by content id)")]
  C --> ZP["Zero projection: upsert documents/folders rows (06)"]
```

## 5. Read path — file ops vs. search hit different stores

```mermaid
flowchart LR
  A["Agent"] -->|"ls/read/write/edit/mv/rm"| B["GitTreeBackend → working copy (02)"]
  B --> GIT["Git (truth)"]
  A -->|"semantic search"| S["hybrid_search (unchanged)"]
  S --> PG[("Postgres chunks + embeddings")]
```

## 6. Live connectors — never stored (out of scope)

```mermaid
flowchart LR
  Q["Chat query"] --> LC["Slack / Gmail (live)"]
  LC -->|"fetched at chat time"| ANS["used in the answer"]
  LC -.->|"never"| GIT["Git"]
  LC -.->|"never"| PG[("Postgres chunks")]
```

## 7. History / undo — git replaces the three hand-rolled systems

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

## 8. Migration (05) — Postgres KB → seed git repo

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

## 9. Reindex (04) — the safety net (Fossil `rebuild`)

```mermaid
flowchart LR
  GIT["Git HEAD (truth)"] --> RB["reindex(workspace)"]
  RB --> WIPE["wipe chunks + embeddings"]
  WIPE --> REBUILD["re-chunk + re-embed all files\n(reuse cache by blob SHA)"]
  REBUILD --> PG[("Postgres index rebuilt")]
```
