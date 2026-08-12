# Git-native KB — Current Flow Diagrams

> Visual companion to [`00-umbrella-plan.md`](00-umbrella-plan.md).

## 1. Shared Git revisions, separate domains

```mermaid
flowchart LR
  GIT["Workspace Git repo\n/documents + /artifacts"] --> DISPATCH{"Root dispatcher"}
  DISPATCH -->|documents/**| DOC["Document projection"]
  DISPATCH -->|artifacts/**| ART["Artifact projection"]
  DOC --> CHUNK[("Chunk")]
  ART --> ACHUNK[("ArtifactChunk")]
  BLOBS[("Blob storage")] --- DOC
  BLOBS --- ART
```

Git stores committed searchable text. Postgres owns domain identity/metadata and blob references. Artifact and document rows are never converted or adopted across roots.

## 2. Write timing

```mermaid
flowchart TD
  NOTE["Document/connector write"] --> WC["Private working copy"]
  SAVE["save_artifact"] --> ADB[("Artifact + ArtifactFile durable")]
  SAVE --> WC
  WC -->|"end of turn"| COMMIT["One Git revision"]
  COMMIT --> PROJECT["Commit-time root projection"]
  COMMIT --> CONVERGE["Async convergence"]
  CONVERGE --> DSEARCH[("Document chunks")]
  CONVERGE --> ASEARCH[("Artifact chunks")]
```

Artifact metadata and bytes are durable before the tool succeeds on Git-backed workspaces. Git commit and search convergence may occur later, and convergence failure does not roll back the artifact. Non-git workspaces index in the save transaction.

## 3. Full-tree convergence

```mermaid
flowchart TD
  HEAD["Git HEAD"] --> SCAN["index_tree"]
  SCAN --> DPATHS["documents/**"]
  SCAN --> APATHS["artifacts/**"]
  DPATHS --> DUPSERT["Upsert/prune Document + Chunk"]
  APATHS --> AUPSERT["Resolve/prune Artifact + ArtifactChunk"]
  AUPSERT --> CURRENT{"indexed_generation == generation?"}
  CURRENT -->|yes| READY["Searchable"]
  CURRENT -->|no| STALE["Excluded; retryable"]
```

The rebuild upserts/prunes; it does not wipe UI-visible identities. Folder reconciliation is document-only. Artifact removal purges artifact blobs and cascades artifact chunks.

## 4. Search

```mermaid
flowchart LR
  Q["Knowledge query"] --> EMB["One query embedding"]
  EMB --> DSEM["Document semantic candidates"]
  EMB --> ASEM["Artifact semantic candidates"]
  Q --> DKEY["Document keyword candidates"]
  Q --> AKEY["Artifact keyword candidates"]
  DSEM --> FUSE["Global reciprocal-rank fusion"]
  ASEM --> FUSE
  DKEY --> FUSE
  AKEY --> FUSE
  FUSE --> GROUP["Group by source_type + source_id"]
  GROUP --> CITE["DOCUMENT_CHUNK or ARTIFACT_CHUNK citations"]
```

Artifact candidates compete globally with documents. Namespaced citation kinds prevent collisions between independent chunk ID sequences.

## 5. Revision and deletion

```mermaid
sequenceDiagram
  participant Agent
  participant API as Artifact service
  participant DB as Artifact tables
  participant Git
  participant Blob

  Agent->>API: revise(artifact_id, expected_generation)
  API->>DB: lock + compare generation
  alt stale
    DB-->>Agent: fail; load source again
  else current
    API->>Blob: stage new role blobs
    API->>DB: replace role rows + increment generation
    API->>Git: update /artifacts representation in working copy
    API-->>Agent: artifact_id + new generation
    API->>Blob: best-effort purge old blobs
  end
```

API deletion removes the Git artifact representation where enabled, deletes the artifact row/chunks/files, then best-effort purges captured blobs. Convergence deletion currently purges best-effort before its row-delete commit; the blob store and database are not atomic. Neither path calls document deletion.

## 6. Document migration

The legacy workspace seed exports documents only. Existing document chunks are adopted by byte parity and incremental indexing starts after the seed revision. Dedicated artifacts are created/indexed by the artifact service and are not migrated or adopted as documents.
