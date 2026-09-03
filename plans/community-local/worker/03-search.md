# Worker — Phase 3: Search

> Implements `backend/shared/search.py` (API calls synchronously).
> Index contract: [`../00c-data-model.md`](../00c-data-model.md) (FTS5 + sqlite-vec, RRF).

## Goal

Hybrid retrieval for chat — keyword + semantic, merged with RRF.

## Work

- `search_workspace(workspace_id, query, top_k)` → ranked chunk hits with `document_id`, line refs, fused score.
- **Query embed** — same model + dimension `D` as ingest.
- **FTS leg:** `chunks_fts` BM25, scoped to workspace via join on `chunks.document_id → documents.workspace_id`, top‑K₁ (e.g. 20).
- **Vector leg:** sqlite-vec KNN on `chunk_vectors`, same workspace filter, top‑K₂ (e.g. 20).
- **Merge:** Reciprocal Rank Fusion (k=60) on the two ranked lists; dedupe by `chunk_id`.
- Unit tests: keyword-only doc, paraphrase query (semantic leg wins), combined case.

## Acceptance

- Ingested doc + lexical query → relevant chunk in top 3.
- Ingested doc + paraphrased query (no shared keywords) → relevant chunk in top 3 via vector leg.
- Empty workspace → empty list, no error.

## Interface to API

Imported in chat route — [`../api/03-chat.md`](../api/03-chat.md).
