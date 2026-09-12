# Worker — Phase 3: Search

> Implements `backend/shared/search.py` (API calls synchronously).
> Index contract: [`../00c-data-model.md`](../00c-data-model.md) (FTS5 + sqlite-vec).

## Goal

Hybrid retrieval for chat — keyword and vector for recall, cosine for order. Both
legs widen the candidate set, then a cosine rescore against the query embedding
decides the final ranking. A cross-encoder reranker is the later opt-in.

## Work — done

`retrieve()` in [`shared/search.py`](../../../surfsense_local/backend/shared/search.py):

- `retrieve(session, workspace_id, query, top_k)` → `Hit`s with `chunk_id`,
  `document_id`, line refs, cosine score. The workspace is the scope; chunks are
  what's searched. An empty or whitespace query returns nothing before it embeds.
- **Query embed** — the bundled encoder in-process, same model + dimension `D` as ingest.
- **Keyword leg (recall):** `chunks_fts` BM25, scoped to workspace via join on
  `chunks.document_id → documents.workspace_id`, top 20. Terms are quoted against
  FTS5's grammar; it only contributes candidates, never the final order.
- **Vector leg (recall):** sqlite-vec KNN on `chunk_vectors` (isolated in a CTE so
  only `MATCH` and `k` constrain it), then the workspace filter, top 20.
- **Rescore (order):** the union of both legs is scored by `vec_distance_cosine`
  against the query vector and cut to `top_k`. Meaning decides the order, so noise
  a keyword match drags in falls below the cut — no stopword list or rank fusion
  needed. The cross-encoder reranker is the documented opt-in that would replace
  this cosine scorer.
- Integration tests run the real encoder end to end: keyword hit, paraphrase (no
  shared keywords, meaning finds it), workspace scoping, empties.

## Acceptance

- Ingested doc + lexical query → relevant chunk in top 3.
- Ingested doc + paraphrased query (no shared keywords) → relevant chunk in top 3 via vector leg.
- Empty workspace → empty list, no error.

## Interface to API

Imported in chat route — [`../api/03-chat.md`](../api/03-chat.md).
