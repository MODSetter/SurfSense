# ADR 0006: Retrieval widens recall with FTS5 and sqlite-vec, then orders the union by cosine similarity

- **Status:** Accepted; the ordering decision, that cosine alone decides and neither a stopword list nor rank fusion is needed, is superseded by [ADR 0031](0031-ranking-blends-absolute-leg-scores.md)
- **Date:** 2026-09-05
- **Source:** [Umbrella plan L105](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00-umbrella-plan.md#L105), [Data model L200–224](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00c-data-model.md#L200-L224), [Search plan L6–31](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/worker/03-search.md#L6-L31)

## Context

Chat answers from the user's own documents, and ingest stores an embedding for every chunk. Search has to use those embeddings properly, not fall back to keywords alone or scan BLOBs in memory, and it has to find an exact term as well as a paraphrase with no shared words. Everything lives in one database file, `surfsense.db` ([ADR 0004](0004-desktop-app-is-its-own-tree.md)). Search as built is in [search](../architecture/search.md).

## Decision

- Two legs widen recall. Each is scoped to the workspace and proposes 20 candidates (`CANDIDATES` in [`shared/search.py`](../../surfsense_local/backend/shared/search.py)).
  - Keyword: FTS5 BM25 over `chunks_fts`, an external-content table that keeps no text of its own and reads it from `chunks`. Query terms are quoted against FTS5's grammar and joined with `OR`.
  - Vector: sqlite-vec KNN over `chunk_vectors`, a `vec0` table whose rowid is `chunks.id`.
- The union is rescored by `vec_distance_cosine` against the query vector and cut to `top_k`. Meaning decides the order, so noise that a keyword match drags in falls below the cut, and no stopword list or rank fusion is needed.
- Three triggers on `chunks` keep the index in step ([`0001_initial_schema.py`](../../surfsense_local/backend/alembic/versions/0001_initial_schema.py)). Insert and update mirror the text into `chunks_fts`; delete removes the chunk from both index tables. A virtual table takes no foreign key, so without them the index would keep answering for deleted documents.
- There is no reranker. A cross-encoder reranker is the documented later opt-in, and it would replace the cosine scorer.

## Consequences

- Keyword matches add reach but never decide order. A chunk that shares words with the query but not its meaning can fall below the cut.
- Ingest has to write each chunk's `vec0` row itself, because only ingest holds the embedding. The FTS row follows by trigger.
- The vector leg runs KNN over the whole index before the workspace filter applies. The `ponytail:` in `shared/search.py` accepts that for a few small workspaces and names the fix: widen `k` if a workspace's hits start falling outside the global top 20.
- Search and ingest have to use the same embedding model and dimension ([ADR 0007](0007-bundled-embeddings.md)).
