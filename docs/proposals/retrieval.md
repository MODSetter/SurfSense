---
status: proposed
code:
  - surfsense_local/backend/worker/ingestion/embedding.py
  - surfsense_local/backend/shared/search.py
  - surfsense_local/backend/alembic/versions/
---

# A multilingual embedder

> The app ships in ten languages and retrieves in one. Same-language search works everywhere; crossing between languages does not, because bge-small-en-v1.5 is English-only. Swapping the embedder closes that, and the re-embed migration is the hard half, not the swap.

Ranking is done: [ADR 0031](../adr/0031-ranking-blends-absolute-leg-scores.md) gave both legs the order, [ADR 0032](../adr/0032-one-tokenizer-for-index-and-question.md) made a term a word in every script, [ADR 0033](../adr/0033-every-candidate-is-scored-on-its-own-cosine.md) stopped an unmeasured chunk scoring zero. The eval reaches an answering passage for 98% of 266 queries. What remains is the embedder, which no ranking change can reach — the gap is in [search](../architecture/search.md).

## The gap, measured

Every number here comes from [`scripts/run_retrieval_eval.py`](../../surfsense_local/backend/scripts/run_retrieval_eval.py) on `dev`, 17 authored documents plus LIMIT-small, 266 queries.

Read the two cases apart, because they behave nothing alike:

- **Same-language** — asking in German about a German document. 100% across German, Japanese, Chinese and Hindi, and still 100% on meaning alone. bge is not the weak link here. It maps same-language text consistently even in scripts it does not model.
- **Cross-language** — asking in English about a Japanese document, or the reverse. 2 of 8 blended, and **1 of 8 on meaning alone**, which is chance. The embedder cannot cross languages, so no weight recovers it.

The same split shows in the raw vectors. Cosine between an English sentence and its translation, minus cosine to an unrelated sentence in that language:

| | ja | hi | de | zh |
|---|---|---|---|---|
| bge-small | +0.086 | **−0.014** | +0.151 | +0.119 |
| granite-97m-r2 | +0.199 | +0.161 | +0.261 | +0.255 |

bge scores Hindi **backwards**: an unrelated Hindi sentence sits closer to the English claim than its own translation.

## The candidate

`ibm-granite/granite-embedding-97m-multilingual-r2`. Apache-2.0, ungated, 52 languages, int8 ONNX. It is a drop-in: `hidden_size` 384 so `vec0` keeps its width and [ADR 0007](../adr/0007-bundled-embeddings.md)'s width check still passes, CLS pooling like bge, and no query prefix — [`embedding.py`](../../surfsense_local/backend/worker/ingestion/embedding.py) needs no change beyond the repo constants.

Swept on `dev`, because `SEMANTIC_WEIGHT` is defined as a plateau measured per embedder and judging a candidate at the incumbent's tuned weight is not a fair test:

| weight | granite cross-lingual | granite limit | granite all | bge cross-lingual | bge all |
|---|---|---|---|---|---|
| 0.65 | 38% | 100% | 98% | 25% | 98% |
| 0.75 | 75% | 100% | 99% | 25% | 98% |
| **0.85** | **88%** | **100%** | **99%** | 12% | 97% |
| 0.90 | 88% | 99% | 98% | 12% | 94% |
| 1.00 | 100% | 34% | 49% | 12% | 50% |

**Granite at 0.85 beats bge's best on every slice but one**, and needs no new machinery — only the weight moves. On meaning alone it scores cross-lingual 100% against bge's 12%, so the embedding solves the gap outright and the blend is what gives some of it back.

## Decisions

- **Take granite-97m-r2**, and retune `SEMANTIC_WEIGHT` from 0.65 to 0.85 in the same change, with its own ADR amending [ADR 0031](../adr/0031-ranking-blends-absolute-leg-scores.md). The weight is not a free parameter to leave at the old model's plateau.
- **Rejected: a cosine floor.** Cosine does not reach zero on real text — unrelated passages bottom out near 0.62 for bge and 0.75 for granite — so the semantic leg never truly abstains, and rescaling from a floor also recovers cross-lingual. It was tried and dropped: 0.65 suits the eval's document chunks and zeroes a correct match on one-line notes, so the constant tracks text length as much as model. The weight retune gets the same result with no constant.
- **Rejected: EmbeddingGemma-300M.** The licence was never the blocker — Gemma Terms do permit commercial use. Two other things rule it out: the weights are **gated** (`gated: manual`, anonymous `config.json` returns 401), so the app cannot fetch them at runtime and mirroring them is itself Distribution; and there is **no 384-dim output** (768 native, Matryoshka at 512/256/128), which forces a `vec0` schema change on every existing index.
- **Rejected: `multilingual-e5-small`** (MIT, same speed, materially lower quality) and **Qwen3-Embedding-0.6B** (Apache-2.0, about 4× slower, weak on under-represented languages).
- Do not compare EmbeddingGemma's MTEB 61.15 with granite's 60.3: the first averages every task type, the second is retrieval only. Our own corpus decides it.

## The migration, which is the work

Same width means no schema change, but different weights mean every vector in every library is wrong. Chunks and extracted text are stored, so nothing is re-parsed — this is a re-embed, not a re-ingest.

- The index must **record which model wrote it**. It does not today, and [ADR 0007](../adr/0007-bundled-embeddings.md) names that gap: a same-width replacement is undetectable, so a swapped model silently searches an index built by another one.
- Re-embed in the background and resumable, into a second vector table. Search keeps serving the old vectors and the old query model until the new table is complete; one transaction switches. Chunk ids do not move, so existing citations resolve throughout.
- New uploads during the migration embed into both.
- Rough cost: about 8 minutes per 1,000 passages on a mid CPU, measured on bge and not yet re-measured on granite, which is 3× the parameters.

## Risks

- **The eval cannot see the regression this would cause.** All four same-language slices sit at 100% for both models at every weight — saturated, so they can neither fail nor improve. The per-query diff at 0.65 shows granite pushing same-language answers *down*: `wear-parts-zh` 1 → 5, `osaka-lease-ja` 1 → 4, `replacement-zh` 2 → 3. They stay inside the top 5 on a 63-document corpus; on a real library they would fall out of the prompt. **Harden those slices before starting the migration** — near-tied documents where only one leg can decide, the way `test_a_hindi_question_finds_the_note_that_answers_it` is built.
- Cross-lingual is 8 authored queries. It is the whole case for this change, and it is thin.
- Paraphrase costs one query, and softly: `paraphrase-out-of-hours` moves rank 5 → 6, a threshold miss rather than a disappearance.
- Bundle: granite is 94 MB int8 plus a 24 MB tokenizer, against bge's 63 MB. Note the incumbent is FP16, not int8 as ADR 0007 says, so this is not a like-for-like comparison — an int8 bge would be about 33 MB.

## Open questions

- Does the re-embed run on first launch after update, or wait for the user to ask? A library of any size makes this a visible, long job.
- What happens to a library mid-migration when the app is closed, and what does Settings show while it runs?
- Is 0.85 a plateau or a peak? It was swept at six points; the neighbouring 0.90 already costs LIMIT a point.
