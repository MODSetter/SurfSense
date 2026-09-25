# ADR 0031: Ranking blends the two legs on absolute scales, keyword strength being term coverage rather than BM25

- **Status:** Accepted; amended by [ADR 0032](0032-one-tokenizer-for-index-and-question.md), term coverage being safe only where a term is a word
- **Date:** 2026-09-24
- **Supersedes:** the ordering decision in [ADR 0006](0006-hybrid-retrieval.md), that the union is ordered by cosine similarity alone and needs neither a stopword list nor rank fusion
- **Source:** [retrieval eval](../../surfsense_local/backend/scripts/run_retrieval_eval.py), [ADR 0006](0006-hybrid-retrieval.md)

## Context

[ADR 0006](0006-hybrid-retrieval.md) let a keyword match widen recall but never affect the order, reasoning that cosine would drop the noise a keyword match drags in. That was written without a way to measure it. The retrieval eval now indexes a fixed corpus through the real ingest pipeline and asks `retrieve()` every query, and it showed the cost: an answering passage reached the prompt for 50% of 266 queries, and a bare asset tag returned manuals in other languages while the document holding the tag ranked nowhere. Exact match worked only where the embedder happened to agree, because BM25 had no vote. Search as built is in [search](../architecture/search.md).

## Decision

- Both legs decide the order. Each candidate scores `0.65 × semantic + 0.35 × keyword`, and a candidate missing from a leg takes nothing from it rather than a penalty.
- **Each leg's score is absolute**, meaning the same thing from one query to the next, so a leg with nothing to say contributes nothing. This matters more than the weight.
  - Keyword strength is the fraction of the query's distinct terms a chunk matched, one indexed lookup per term over the candidates BM25 returned. BM25 itself is kept only to pick and order those candidates.
  - Semantic strength is cosine similarity, floored at zero: a passage pointing the other way is no evidence rather than evidence against.
- `SEMANTIC_WEIGHT` is the middle of a measured plateau. Swept from 0 to 1, the corpus is flat at 98% across 0.6 to 0.65 and falls away either side.
- Rejected, both measured on the same corpus: **reciprocal rank fusion** (88%), and **min-max normalising** either leg within a query (89% at the same weight).
- `Hit.score` stays cosine similarity. It says how close a passage is; it no longer says where the passage sits.

## Consequences

- An answering passage reaches the prompt for 98% of the eval's queries against 50%, at mean rank 1.1 against 3.7. Identifier lookups go from 75% to 100% and LIMIT-small from 38% to 100%.
- A keyword match can now decide the order, which ADR 0006 ruled out. Term coverage is what makes that safe: a chunk matching one term of five is weak on an absolute scale, so no stopword list is needed to keep it down. Rank fusion, which discards strength, is what would need one — asked "a cat napping in sunlight", it returned a note matching only "a" and "in", because being in both legs beats topping one.
- A query costs one further indexed FTS5 lookup per distinct term. The `ponytail:` in [`shared/search.py`](../../surfsense_local/backend/shared/search.py) names an `fts5vocab` table as the fix if queries ever get long.
- Cross-lingual retrieval falls from 50% under rank fusion to 25%. Cosine alone scores 12%, so the embedder cannot cross languages and rank fusion was inflating a signal sitting outside the top 5. A multilingual embedder is the fix; the ranking is not.
- Neither the index nor the stored vectors change, so this needs no migration and no re-embed.
