# Search

`retrieve()` finds the passages in a workspace that best answer a query. Two legs widen recall, a keyword match and a nearest-neighbour search over embeddings, and their union is then ordered by cosine similarity to the query, so meaning decides the order and keywords only add reach. It runs in the calling process against the same SQLite file as everything else, and chat is its only caller.

**Code:** [`shared/search.py`](../../surfsense_local/backend/shared/search.py), [`worker/ingestion/embedding.py`](../../surfsense_local/backend/worker/ingestion/embedding.py)
**Decisions:** [ADR 0006](../adr/0006-hybrid-retrieval.md), [ADR 0007](../adr/0007-bundled-embeddings.md)

## Interface

```python
retrieve(session, workspace_id, query, top_k=5, document_ids=None) -> list[Hit]
```

- A `Hit` carries `chunk_id`, `document_id`, the document's `title`, the passage `content`, `start_line`, `end_line` and `score`, which is 1 minus the cosine distance. Hits come back best first.
- The workspace is the scope; chunks are what is searched.
- `document_ids` narrows the scope to those documents. `None` searches the whole workspace, and an empty list returns nothing. Chat passes the ready documents the user left included in the sources panel ([`chat.md`](chat.md)).
- A blank query returns nothing before anything is embedded.

## How it ranks

1. **Embed the query** with the bundled bge-small model at the same width as ingest. The import is lazy, so onnxruntime and the model load on the first query rather than when the API starts.
2. **Keyword leg.** The query is split into word tokens, lowercased, each quoted against FTS5's query grammar and joined with `OR` to keep recall wide. `chunks_fts` is matched, joined to `chunks` and `documents` for the workspace and document filters, and the best 20 by BM25 are kept.
3. **Vector leg.** A sqlite-vec nearest-neighbour search over `chunk_vectors` takes the 20 closest chunks. It sits in its own CTE, so only `MATCH` and `k` constrain it, as vec0 requires; the workspace and document filters then apply to that set.
4. **Rescore.** The union of both legs is scored with `vec_distance_cosine` against the query vector and cut to `top_k`.

Neither leg decides the order. A keyword match drags in passages that merely share a word, and the cosine rescore lets them fall below the cut, so no stopword list or rank fusion is needed. A paraphrase that shares no words with its passage still arrives through the vector leg. There is no reranker.

## Ceiling

The vector leg looks at the 20 nearest chunks across every workspace before it filters. A workspace, or a document selection, whose passages all rank outside that global 20 gets candidates from the keyword leg only. The code accepts this for a few small local workspaces and names a larger `k` as the fix if a workspace's hits start falling outside it.

## Index

`chunks_fts` is an FTS5 table with external content over `chunks`, and `chunk_vectors` a vec0 table keyed by chunk id. Triggers on `chunks` keep the keyword index in step, including on cascade, and ingest writes the vectors ([`data-model.md`](data-model.md), [`documents.md`](documents.md)). Because both indexes key on chunk ids, a hit is a chunk row, and the citation panel can load that chunk's neighbours by position.

## Tests

[`tests/integration/search/test_retrieve.py`](../../surfsense_local/backend/tests/integration/search/test_retrieve.py) covers a keyword query, a paraphrase found through meaning, the document and lines on a hit, scoping to selected documents and to the workspace, and the empty workspace, query and selection. [`tests/integration/chunks/test_search_index.py`](../../surfsense_local/backend/tests/integration/chunks/test_search_index.py) covers the triggers and the refusal of a vector of the wrong width.

## Known gaps

- None.
