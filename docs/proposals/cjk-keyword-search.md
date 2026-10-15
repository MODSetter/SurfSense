---
status: proposed
tracking: https://github.com/MODSetter/SurfSense/issues/1997
code:
  - surfsense_local/backend/shared/tokenizer.py
  - surfsense_local/backend/worker/ingestion/indexing.py
  - surfsense_local/backend/alembic/versions/
---

# Keyword search in Japanese and Chinese

> Normalize text with NFKC, then split each run of Han or katakana into overlapping two-character terms, treating hiragana as a separator, for the index and the question alike. With today's embedder, this lifts the top 5 for natural-language questions from 56 to 77 in Japanese and from 47 to 75 in Chinese. With the multilingual embedder the [retrieval proposal](retrieval.md) recommends, the same questions already reach 92 and 91, and segmenting leaves them within noise. What it still adds there is a keyword leg that finds the passage, and full-width input (`Ｘ４００`) that is found at all. No query outside CJK loses its top-5 answer under either embedder.

`unicode61` ends a token only at a separator, and Japanese and Chinese are written without spaces, so a whole clause becomes one term ([search](../architecture/search.md), Known gaps). [ADR 0032](../adr/0032-one-tokenizer-for-index-and-question.md) rejected `trigram` for this and left the gap open.

## How it was measured

The measurements live in a separate repository, [surfsense-cjk-eval](https://github.com/vintcessun/surfsense-cjk-eval), so that SurfSense takes in no dataset or eval code for them. It runs against an unmodified checkout, `dev` at `cddfd05f9`. It imports SurfSense's own retrieval, ingest and database code and the eval's scorer, and changes only what a variant names: the keyword table, the rule that splits a question, or the coverage score.

- **The data.** SurfSense's authored eval corpus and LIMIT-small, plus 100 Japanese and 100 Chinese MIRACL questions with all 1,757 Wikipedia passages judged for them, hard negatives included. All of it is indexed into one workspace through the ingest pipeline: 466 queries. The authored CJK slices alone cannot decide this. They hold five questions each, and on a corpus that small all of them already reach the top 5 on meaning alone.
- **A synthetic slice.** The 20 authored English and identifier queries, retyped in full-width characters as a Japanese or Chinese IME produces them, measure normalization. They are left out of every total.
- **Both embedders.** bge-small at SurfSense's semantic weight of 0.65, and granite-embedding-97m-multilingual-r2 at the 0.85 the retrieval proposal measured for it.
- **Fixed in advance.** The repository's README states how results would be read before any variant ran. The deciding measure is the natural-language one, MIRACL's top 5 and MRR. No slice without CJK may lose a top-5 answer, and every query that moves there is listed. Between close variants, fewer moving parts win. Two variants were added after a first look, and the README says which and why.

## What today's index does

With bge, among MIRACL's passages:

- **The keyword leg proposes the answer for 34% of Japanese questions and 1% of Chinese ones**, among its 20 candidates. A Chinese question is one term, and a Japanese one is 1.6 terms on average.
- **The authored questions collapse in a real library.** Japanese falls to 3 of 5 in the top 5 and Chinese to 1 of 5, against 5 of 5 on the authored corpus alone.
- **CJK passages distort English questions.** A CJK clause indexed as one term makes its chunk look short to BM25, so a chunk that also holds `the` or `of` outranks English chunks for those words. For `paraphrase-out-of-hours`, 11 of the keyword leg's 20 candidates are Japanese passages matching only `of` and `the`, and the answer is not among them. Its answer drops out of the top 10.
- **Full-width input finds nothing.** `Ｘ４００` and `x400` are different terms to `unicode61`, so 0 of the 20 full-width queries reach the top 5.

## The variants

Top 5 out of 100 per MIRACL slice, the sum over all 466 real queries, and the full-width slice:

| Variant | bge: ja / zh / all | granite: ja / zh / all | full-width, bge / granite | keyword index (bge) |
|---|---|---|---|---|
| today | 56 / 47 / 356 | 92 / 91 / 445 | 0 / 0 | 1.06 MB |
| abstain on CJK questions | 44 / 46 / 340 | 95 / 91 / 448 | 0 / 0 | 1.06 MB |
| idf-weighted coverage | 57 / 47 / 357 | 92 / 91 / 446 | 0 / 0 | 1.06 MB |
| NFKC | 56 / 47 / 356 | 92 / 91 / 445 | 15 / 19 | 1.05 MB |
| `trigram` | 78 / 68 / 401 | 93 / 90 / 443 | 0 / 0 | 3.48 MB |
| bigrams over Han and kana | 77 / 75 / 410 | 92 / 91 / 446 | 0 / 0 | 1.56 MB |
| unigrams + bigrams | 77 / 81 / 417 | 90 / 92 / 445 | 0 / 0 | 2.43 MB |
| bigrams, hiragana as separator | 77 / 75 / 411 | 92 / 91 / 446 | 0 / 0 | 1.11 MB |
| **the same, with NFKC** | **77 / 75 / 411** | **92 / 91 / 446** | **15 / 19** | **1.11 MB** |
| the same, with NFKC and idf | 77 / 79 / 414 | 93 / 90 / 447 | 14 / 18 | 1.11 MB |
| dictionary (jieba, Sudachi; language known) | 71 / 78 / 407 | 91 / 92 / 446 | 0 / 0 | 0.83 MB + ~100 MB |

The repository's summary has every slice, MRR, the keyword leg's recall and terms per question, and each moved query.

- **Abstaining is worse under bge** (356 → 340). A Japanese question's Latin terms, such as a model name, are what currently find its answer. Under granite, the three extra Japanese answers are within noise.
- **idf weighting does nothing on its own**, since a CJK question is still one term. On top of segmenting, it is mixed: four more Chinese answers under bge, one fewer under granite, and seven LIMIT ranks moved under granite. It also rewrites [ADR 0031](../adr/0031-ranking-blends-absolute-leg-scores.md)'s score for every language. Not worth it on this evidence.
- **NFKC changes nothing but what it is for.** Every one of the 446 real queries ranks exactly as today under both embedders, and full-width queries go from 0 to 15 and 19.
- **`trigram`** moves 14 queries without CJK under bge and 45 under granite, LIMIT among them. A two-character Chinese word cannot match a three-character gram.
- **The dictionary** is an upper bound, not a candidate. It needs about 100 MB of dictionaries and a language-identification step the app does not have, since Han-only text cannot be assigned to Japanese or Chinese by itself. It is not better.
- **Hiragana as separator, against plain bigrams.** Content words are written in kanji and katakana, and hiragana mostly carries grammar. Ignoring it halves a Japanese question's terms (8.8 against 15.4) and gives an index 5% larger than today's rather than 48% larger, at equal results. Chinese has no hiragana, so its numbers are identical.

## Every query that moves outside CJK, for the chosen variant

- **bge**: `paraphrase-out-of-hours`, from outside the top 10 to rank 5. Any variant that indexes CJK as words moves this query, because the distortion described above goes away.
- **granite**: `limit-query_265` from rank 2 to 1, and `limit-query_323` from 3 to 2.

No query outside CJK loses rank.

Among the CJK slices, one cross-lingual query pays under bge. `cleaning-asked-in-japanese` asks in Japanese about the English X200 manual and falls from rank 2 to 9. It matched only through `X200`, one of its two terms, and becomes one of several. Under granite, the cross-lingual slice keeps 6 of 8. Asking across languages is the embedder's gap.

## The recommendation

`segment()` = NFKC, then bigrams over Han and katakana with hiragana as a separator, for the index and the question.

- **Under bge**, it is the large fix for natural-language questions: 356 → 411 over all queries.
- **Under granite**, natural-language questions are neutral, and the change carries what the embedder cannot:
  - the authored Japanese questions reach 5 of 5, up from 4;
  - the keyword leg finds the passage for 99% of CJK questions, up from 34% and 1%, which is what an exact name, a code or a rare term depends on;
  - full-width input works.
- **The cost**:
  - words written wholly in hiragana are no longer keyword-searchable (`りんご`, `ください`), though the semantic leg still reaches them;
  - under bge, the one cross-lingual query above falls;
  - Korean is untouched, since it already separates words with spaces;
  - Han outside the Basic Multilingual Plane is not segmented.
- **Order relative to the embedder.** If granite lands first, this matters less for natural-language questions but still fixes exact terms and full-width input. NFKC alone is the smallest change with a gain under both embedders and no movement elsewhere. Its index change is the same as segmenting's, though, so shipping NFKC without segmenting saves almost nothing.

### What a term means afterwards

[ADR 0031](../adr/0031-ranking-blends-absolute-leg-scores.md) scores the fraction of a question's terms a chunk matched, and relies on a term being a word. A bigram is sometimes not a word: `退货运费` yields `货运` across a word boundary. The chosen split keeps a Japanese question at about nine terms, close to the dictionary's eight, and the keyword leg's recall shows those terms find the answer. idf weighting was the candidate fix for spurious pairs, and it did not earn its cost.

## How it is built

- **One rule.** `shared/tokenizer.py` gains `segment(text)`. `terms()` asks FTS5 for the terms of `segment(question)`. The tokenizer literal stays `unicode61 categories 'L* N* Co M*'`.
- **No text stored twice.** Python's `sqlite3` cannot register an FTS5 tokenizer, so `segment()` runs in Python:
  - `chunks_fts` becomes a contentless table with `contentless_delete=1`.
  - `indexing.replace_chunks()`, the only writer of chunks for ingest and Studio alike, inserts `segment(content)` under each chunk's id.
  - A delete trigger removes rows by id. The insert and update triggers go.
  - `contentless_delete` needs SQLite 3.43, and the uv-managed Python 3.12 that CI freezes the app with ([packaging](../architecture/packaging.md)) has SQLite 3.47.1.
- **Migration.** A new revision recreates `chunks_fts`, replaces the triggers, and fills the index by segmenting every chunk in Python. There is no re-embed and no download. Measured at 6.5 seconds per 100,000 chunks. `0017` is not edited.
- **Cost per question.** Splitting a question goes from 238 to 269 µs, against the ~50 ms its embedding costs.
- **The eval.** A version constant for `segment()` joins `TOKENIZER` in the index fingerprint.

## Ship

Once a variant is agreed:

1. **Tests first:**
   - a Japanese and a Chinese copy of `test_a_hindi_question_finds_the_note_that_answers_it`, each three notes one word apart;
   - a full-width question finding its note;
   - CJK and full-width text in the index-and-question test in `test_search_index.py`.
2. **Code:** `segment()`, the contentless index, the revision, and the fingerprint.
3. **An ADR** amending ADR 0032's "Rejected for CJK".
4. **Docs:** the Known-gaps line in [`search.md`](../architecture/search.md) deleted, its **Index** and **How it ranks** sections updated, and this proposal deleted.
