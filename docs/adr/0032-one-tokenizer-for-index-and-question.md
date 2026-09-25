# ADR 0032: The index and the question are split by one tokenizer, FTS5's own, and it keeps a word's combining marks

- **Status:** Accepted
- **Date:** 2026-09-24
- **Amends:** [ADR 0031](0031-ranking-blends-absolute-leg-scores.md), whose term coverage is safe only where a term is a word
- **Source:** [retrieval eval](../../surfsense_local/backend/scripts/run_retrieval_eval.py), [ADR 0031](0031-ranking-blends-absolute-leg-scores.md)

## Context

[ADR 0031](0031-ranking-blends-absolute-leg-scores.md) gave the keyword leg 35% of the order and argued no stopword list is needed, because coverage is absolute: a chunk matching one term of five is weak whatever BM25 says. That reasoning holds for a term that is a word.

FTS5's `unicode61` ends a token at every combining mark, so Devanagari `स्कैनर` (scanner) was indexed as `स` + `नर` and `बैटरी` (battery) as `ब` + `टर` — letters, not words. Python's `\w` excludes marks too, so the query was cut the same way and the two happened to agree on nonsense. Nearly every Hindi document holds nearly every Devanagari letter, so coverage stopped discriminating: measured across the eval corpus, the right document covered 96% of a Hindi question's terms and the best wrong document 85%, one pair tying at 91%. A healthy slice is the identifier one, at 86% against 22%. The app ships in [eight languages](../architecture/localization.md), Hindi among them.

## Decision

- **`M*` joins the tokenizer's categories**, so a combining mark stays inside its word. Latin, digits and identifiers tokenise identically either way; this costs them nothing.
- **One rule splits both the index and the question**, stated in [`shared/tokenizer.py`](../../surfsense_local/backend/shared/tokenizer.py) and asked of FTS5 itself rather than matched by a regex. The question is tokenised by inserting it into a throwaway in-memory FTS5 table declared with the same option and reading the terms back.
- Rejected: **replicating the rule in Python**. `unicode61` also folds Latin diacritics, so `café` indexes as `cafe`; a regex agreeing with that needs SQLite's own curated table, and every drift is a wrong vote rather than a miss. Measured, fixing only the index side dropped a Hindi question's coverage to 0 of 10 terms.
- Rejected for CJK: the **`trigram`** tokenizer, which would segment Japanese and Chinese but changes what BM25 means for every other language and grows the index. That gap stays open.

## Consequences

- A Hindi question's coverage margin over the best wrong document goes from +11% to +42%, the wrong document falling from 85% to 27%. Every other slice of the eval is unchanged to the digit, the blend still reaching an answering passage for 98% of 266 queries at mean rank 1.1.
- The eval's index fingerprint now covers the tokenizer beside the corpus and the embedder. Left out, a tokenizer change scored against an index built under the old rule and reported the old rule's numbers.
- Splitting a question costs a throwaway SQLite connection, about 355µs against the ~50ms its own embedding costs, once per `retrieve()`. The `ponytail:` in [`shared/tokenizer.py`](../../surfsense_local/backend/shared/tokenizer.py) names a thread-local connection as the fix at 31µs.
- Migration `0017` rebuilds `chunks_fts`. The index holds no text of its own, so it rebuilds from `chunks` with no re-embed and no download.
- Bengali, Tamil, Thai and every other script that writes with combining marks gain the same correction, untested here.
