# ADR 0003: Generated deliverables are a document type, not a second corpus

- **Status:** Accepted
- **Date:** 2026-08-13
- **Relates to:** [ADR 0001](0001-git-native-knowledge-base.md) (git is the source of truth, Postgres is derived) and [ADR 0002](0002-knowledge-core-ports-and-adapters.md) (one core, many adapters). This ADR decides where a *generated deliverable* lives inside that model.
- **Specs:** [`plans/artifacts/artifacts-overhaul.md`](../../plans/artifacts/artifacts-overhaul.md), [`plans/git-native-kb/00c-shared-contract.md`](../../plans/git-native-kb/00c-shared-contract.md) C1/C5.

---

## Context

A generated deliverable (PDF, DOCX, PPTX, XLSX, Markdown) has state the document model does not represent: an adapter `format`, rendered bytes in durable `primary`/`preview` roles, an optimistic `generation` for later-turn revision, a signed verification receipt, and the tool-call provenance that produced it. That part is uncontroversial — it needs its own tables.

The question is the **searchable text**. Every deliverable also has a Markdown body that must be committed to git, chunked, embedded, ranked, cited, and pruned. Two shapes were available:

1. Give the artifact domain its own body: `Artifact.search_content`, an `/artifacts/**` git root, an `ArtifactChunk` table, an artifact leg in hybrid search, and an `ARTIFACT_CHUNK` citation kind.
2. Make the body an ordinary `Document` with a new `document_type`, and keep `Artifact` as a sidecar.

Shape 1 is the natural read of "artifacts are not documents", and it is what the domain-boundary instinct produces. Following it through the whole pipeline is what changed the answer: the file is Markdown in a git tree either way, so every stage downstream of "it is text" had to be duplicated to serve a distinction that only matters at the delivery surface.

## Decision

**An artifact's searchable body is a `Document` with `document_type = ARTIFACT`. `Artifact`/`ArtifactFile` are sidecars.**

- `Document` owns title, path (`documents/<title>.md`), Markdown, content hash, folder, and indexing status.
- `Artifact` owns `format`, `generation`, provenance, verification metadata, and `document_id` — a non-null unique cascading key. It owns **no** title, path, body, hash, or indexing state.
- `ArtifactFile` owns one immutable blob per durable role: `primary` or `preview`. Generation source files are transient sandbox inputs, not persisted artifact files. Binary bytes never enter git and never become `DocumentFile` rows.
- One projected git root, one `Chunk` table, one search leg, one citation namespace.
- `document_type` earns exactly three behaviors: the library badge, the type filter, and the editor's read-only guard. Nothing in storage, convergence, or retrieval branches on it.

## Consequences

### Positive

- **One of everything instead of two.** No artifact chunk table, root dispatcher, prune map, search leg, rank-fusion merge, citation kind, marker prefix, or chunk-context route. Every one of those was a place two implementations could drift.
- **Rename, move, and delete have one implementation.** The old shape had `Artifact.title` and a document title as candidate homes for the same string; dropping the column removed the class of bug where a rename updates one and search returns the other.
- **Type filters and `@`-mentions come free.** A deliverable is pinnable and excludable because it is a document. A parallel corpus would have needed both features reimplemented to reach parity.
- **Fair ranking without special-casing.** Artifact passages compete in the same reciprocal-rank fusion rather than being merged in as a second result list.
- **Blob purge is reachable from the document.** The document purge path collects `ArtifactFile` keys through `artifact.document_id`, so no caller has to know which kind of document it deleted to avoid leaking blobs.

### Negative / cost

- **`document_type` becomes load-bearing in convergence.** Row upsert must resolve by `path` and preserve the existing row's type; if a rebuild ever re-derives it, every deliverable silently demotes to a note and its badge, filter, and read-only guard all fail at once. This is the single most important invariant the decision creates.
- **Read-only is now an obligation, not a structural guarantee.** A separate corpus could not be opened by the document editor at all. Because the body is a document, the editor's save path must refuse `ARTIFACT` server-side — the frontend's editable-type set is a UX affordance, not the guard.
- **Corpus-wide content-hash dedup must be bypassed.** `prepare_for_indexing` drops a document whose Markdown hash already exists, which is correct for a re-synced connector page and wrong for a deliverable with its own identity, roles, and generation. `save_artifact` constructs the row directly and calls `index()`.
- **Save is no longer one transaction on non-git workspaces.** `IndexingPipelineService.index()` commits mid-flow, so an embedding failure leaves a durable artifact with a `failed` document instead of rolling the save back. Accepted deliberately: losing a verified deliverable because an embedding provider was down is worse than a retryable index.
- **The stale-generation window is now the ordinary document window.** A revision's passages trail its bytes by one convergence run, so search can quote the previous generation's text while the manifest serves the current file. The old shape hid this by gating search on `indexed_generation == generation`; that gate is gone, because it does not exist for documents and reintroducing it for one type would recreate the artifact-specific search leg this ADR removes. The panel reads the manifest, so what the user opens is always current.
- **The enum member is permanent.** PostgreSQL cannot drop an enum value, so a downgrade leaves `ARTIFACT` in `documenttype` with no rows using it.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Separate artifact corpus (`/artifacts/**`, `ArtifactChunk`, artifact search leg, `ARTIFACT_CHUNK`) | Duplicates the entire text pipeline to preserve a distinction that only matters at the delivery surface, and still has to reimplement type filters and mentions to reach parity. |
| `document_metadata` flag instead of an enum value | A discriminator that drives filters and a badge needs to be queryable and indexable. A JSON flag is neither, and it leaves the read-only guard depending on a field any writer can drop. |
| Keep `Artifact.title` alongside `Document.title` | Two homes for one string. The only way a rename cannot desynchronize them is for one of them not to exist. |
| Hide deliverables in a system folder | The folder is visible and normal. Hiding it would mean a second listing path and a document the user can find by search but not by browsing. |

## Obligations

1. Convergence and projection preserve an existing row's `document_type`; `NOTE` is invented only for a git file no row claims.
2. `save_document` refuses `document_type = ARTIFACT`. Rename, move, and delete stay legal.
3. `save_artifact` does not route through connector preparation.
4. `save_artifact` withholds the knowledge-store path marker until projection lands, so a rebuild cannot read an uncommitted deliverable as an orphan to prune.
5. Blob purge resolves artifact roles through `artifact.document_id`.
