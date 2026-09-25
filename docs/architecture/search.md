# Search

`retrieve()` finds the passages in a workspace that best answer a query. Two legs widen recall, a keyword match and a nearest-neighbour search over embeddings, and a weighted blend of the two decides the order, meaning counting for rather more than words. It runs in the calling process against the same SQLite file as everything else, and chat is its only caller.

**Code:** [`shared/search.py`](../../surfsense_local/backend/shared/search.py), [`shared/tokenizer.py`](../../surfsense_local/backend/shared/tokenizer.py), [`worker/ingestion/embedding.py`](../../surfsense_local/backend/worker/ingestion/embedding.py)
**Decisions:** [ADR 0006](../adr/0006-hybrid-retrieval.md), [ADR 0007](../adr/0007-bundled-embeddings.md), [ADR 0031](../adr/0031-ranking-blends-absolute-leg-scores.md), [ADR 0032](../adr/0032-one-tokenizer-for-index-and-question.md), [ADR 0033](../adr/0033-every-candidate-is-scored-on-its-own-cosine.md)

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
2. **Keyword leg.** The query is split into terms by the index's own tokenizer, each quoted against FTS5's query grammar and joined with `OR` to keep recall wide. `chunks_fts` is matched, joined to `chunks` and `documents` for the workspace and document filters, and the best 20 by BM25 are kept. Each candidate then scores the fraction of the query's distinct terms it matched, one further lookup per term.
3. **Vector leg.** A sqlite-vec nearest-neighbour search over `chunk_vectors` takes the 20 closest chunks. It sits in its own CTE, so only `MATCH` and `k` constrain it, as vec0 requires; the workspace and document filters then apply to that set. It proposes those chunks and does not score them.
4. **Blend.** `0.65 × semantic + 0.35 × keyword` over the union, cut to `top_k` with cosine breaking a tie. Semantic strength is each candidate's own cosine similarity, floored at zero, measured here for the whole union rather than taken from the vector leg ([ADR 0033](../adr/0033-every-candidate-is-scored-on-its-own-cosine.md)). A candidate the keyword leg is missing contributes nothing from it, that absence being a measurement.

Both legs decide the order, and both score on a scale that means the same thing from one query to the next, so a leg with nothing to say adds nothing. That is what keeps a keyword match honest: a chunk matching one term of five is weak whatever BM25 says about it, so no stopword list is needed. It holds because a term is a word: [`shared/tokenizer.py`](../../surfsense_local/backend/shared/tokenizer.py) states the one rule that splits both the index and the question, and keeps a combining mark inside its word so Devanagari is not cut into letters ([ADR 0032](../adr/0032-one-tokenizer-for-index-and-question.md)). A paraphrase that shares no words with its passage still arrives through the vector leg. There is no reranker.

The two legs are asymmetric on purpose. A chunk the keyword leg omits matched none of the query's terms, so zero is what it measured; a chunk the vector leg omits merely sits outside the nearest 20, which says nothing about it. Scoring the second as zero let a crowded workspace next door decide what a quiet one ranked first.

`Hit.score` is cosine similarity, so it says how close a passage is, not where it sits.

## Ceiling

The vector leg looks at the 20 nearest chunks across every workspace before it filters. A workspace, or a document selection, whose passages all rank outside that global 20 gets candidates from the keyword leg only. Those candidates are still ranked on their real cosine ([ADR 0033](../adr/0033-every-candidate-is-scored-on-its-own-cosine.md)), so the order holds; what a crowded neighbour still costs is a passage reachable by meaning alone, which is then proposed by nothing. The code accepts this for a few small local workspaces and names a larger `k` as the fix if a workspace's hits start falling outside it.

## Index

`chunks_fts` is an FTS5 table with external content over `chunks`, declared with the tokenizer `shared/tokenizer.py` names, and `chunk_vectors` a vec0 table keyed by chunk id. Triggers on `chunks` keep the keyword index in step, including on cascade, and ingest writes the vectors ([`data-model.md`](data-model.md), [`documents.md`](documents.md)). Because both indexes key on chunk ids, a hit is a chunk row, and the citation panel can load that chunk's neighbours by position.

## Tests

[`tests/integration/search/test_retrieve.py`](../../surfsense_local/backend/tests/integration/search/test_retrieve.py) covers a keyword query, a paraphrase found through meaning, a Hindi question against three notes one word apart, a workspace whose neighbour holds every one of the 20 nearest chunks, the document and lines on a hit, scoping to selected documents and to the workspace, and the empty workspace, query and selection. [`tests/integration/chunks/test_search_index.py`](../../surfsense_local/backend/tests/integration/chunks/test_search_index.py) covers the triggers, the refusal of a vector of the wrong width, and that the index and a question split text the same way — the migration and [`shared/tokenizer.py`](../../surfsense_local/backend/shared/tokenizer.py) state the tokenizer separately, and a drift between them scores a question against terms the index never held.

Ranking itself is measured rather than asserted, by [`scripts/run_retrieval_eval.py`](../../surfsense_local/backend/scripts/run_retrieval_eval.py): it indexes a fixed corpus through the real ingest pipeline and records where each query's answering passage landed. Failures that need a library-sized corpus, a bare identifier among near-duplicate manuals being the one that drove [ADR 0031](../adr/0031-ranking-blends-absolute-leg-scores.md), do not reproduce at the handful of documents an integration test builds.

## Known gaps

- A question in one language does not find its answer in another. Cosine alone puts the answering passage in the top 5 for 1 of 8 such queries, and the blend for 2 of 8: bge-small is English-only, so no ranking recovers it. A multilingual embedder is the fix.
- FTS5's tokenizer keeps a Japanese or Chinese clause as one token, so the keyword leg finds nothing in those scripts and the blend runs on meaning alone there. `trigram` would segment them at the cost of what BM25 means everywhere else ([ADR 0032](../adr/0032-one-tokenizer-for-index-and-question.md)).
