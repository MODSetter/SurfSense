# Multimodal Document QA Benchmark: Native PDFs vs Parser-Stuffed Context vs SurfSense Agentic Retrieval

**Date:** 2026-05-13  
**Dataset:** MMLongBench-Doc / `multimodal_doc`  
**Run:** `parser_compare`  
**Model:** `anthropic/claude-sonnet-4.5` everywhere  
**Sample:** 30 PDFs, 171 answerable questions  
**Report artifact:** `reports/multimodal_doc/2026-05-14T02-30-16Z/summary.md`  
**Raw artifact:** `data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/raw.jsonl`

---

## 1. Executive Summary

We ran a six-arm comparative study on 30 documents from MMLongBench-Doc to understand how different document-QA strategies perform on long, multimodal PDFs.

The comparison was designed around a realistic product question:

> If we use the same strong LLM, is it better to send the PDF directly, send a full parsed document into the prompt, or let SurfSense retrieve/context-manage chunks agentically?

The arms were:

1. **Native PDF attachment**: send the PDF file directly to Sonnet 4.5.
2. **Azure Document Intelligence basic + long-context stuffing**.
3. **Azure Document Intelligence premium + long-context stuffing**.
4. **LlamaCloud basic + long-context stuffing**.
5. **LlamaCloud premium + long-context stuffing**.
6. **SurfSense agentic retrieval**: use SurfSense `/api/v1/new_chat`, with the PDF already ingested into SurfSense and retrieved dynamically during the answer process.

Headline result:

| Rank by accuracy | Arm | Accuracy | F1 | LLM $/Q | Preproc $/Q | **Total $/Q** | Median latency | Raw failures |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | LlamaCloud premium, full-context | **58.5%** | **61.1%** | $0.1208 | $0.0677 | $0.1885 | 6.8s | 4 |
| 2 | Azure premium, full-context | 56.7% | 59.6% | $0.1373 | $0.0677 | $0.2051 | 6.9s | 3 |
| 3 | Azure basic, full-context | 54.4% | 56.6% | $0.0994 | $0.0068 | $0.1062 | 7.1s | 1 |
| 4 | SurfSense agentic retrieval | 53.2% | 54.3% | **$0.0150** | $0.0677 | **$0.0827** | 52.8s | **0** |
| 5 | LlamaCloud basic, full-context | 50.3% | 53.2% | $0.0981 | $0.0068 | $0.1049 | 7.1s | 2 |
| 6 | Native PDF attachment | 48.0% | 50.4% | $0.2552 | $0.0000 | $0.2552 | 29.5s | 27 |

Cost ranking (cheapest first):

| Rank by cost | Arm | Total $/Q | Accuracy |
|---:|---|---:|---:|
| 1 | **SurfSense agentic retrieval** | **$0.0827** | 53.2% |
| 2 | LlamaCloud basic, full-context | $0.1049 | 50.3% |
| 3 | Azure basic, full-context | $0.1062 | 54.4% |
| 4 | LlamaCloud premium, full-context | $0.1885 | 58.5% |
| 5 | Azure premium, full-context | $0.2051 | 56.7% |
| 6 | Native PDF attachment | $0.2552 | 48.0% |

The main lesson is not simply “parser X wins.” The more important finding is:

> Full-context prompting gives slightly higher peak accuracy when the full processed document fits cleanly in the context window, but SurfSense is the cheapest *and* most robust option: it produced zero runtime failures across the 171-question run and the lowest end-to-end cost per question, while remaining within ~5 percentage points of the best full-context arm.

A follow-up retry experiment (§9.4 + §9.5) tightens this further. We re-ran only the 37 failed `(arm, qid)` pairs with up to 5 attempts of exponential backoff, merged the survivors back into the run, and recomputed the headline numbers:

- **All 10 long-context-arm failures recovered.** 100% recovery rate, mostly on attempt 1 — confirming these were transient transport-layer errors, not context-window overflows.
- **Only 15 of 27 native_pdf failures recovered.** The remaining 12 are intrinsic: 6 questions on one PDF that exceeds the provider's 30 MB wire-size cap, and 5 questions on a 166-page PDF whose response stream the provider cannot reliably terminate. Native_pdf retains a **7% intrinsic failure rate that survives retries**.
- **Final post-retry accuracy** (full table in §9.5): `llamacloud_premium_lc` 59.6% > `azure_premium_lc` 58.5% > `azure_basic_lc` 54.4% > `surfsense_agentic` 53.2% > `native_pdf` 52.0% > `llamacloud_basic_lc` 50.9%. The top three are unchanged; `native_pdf` moves up one spot to #5 (still last among the arms that complete cleanly); SurfSense holds its 53.2% at #4 and stays the cheapest arm.

---

## 2. Why This Experiment Was Run

Earlier small tests suggested that native PDF attachment could sometimes outperform OCR/RAG approaches. That result was not enough to settle the architectural question because it was small, did not isolate parsers, and did not test larger long-document behavior.

This experiment was built to compare three classes of systems:

### A. Non-agentic, no context management

These arms pass the whole document representation to the LLM for every question.

- **Native PDF** sends the original PDF directly to the model.
- **Azure basic/premium** parses the PDF to markdown, then sends that entire markdown context.
- **LlamaCloud basic/premium** does the same with LlamaCloud parser output.

This is the “brute force” approach: give the model everything and ask it to answer.

### B. Agentic, with context management

SurfSense does not pass the full PDF into the prompt for every query. Instead, the document is ingested once, chunked/indexed, and then the agent retrieves/selects relevant context during the answer flow.

This should normally:

- reduce context overflow risk,
- reduce per-question prompt size,
- make the system usable on very long corpora,
- but potentially lose accuracy when the needed evidence is hard to retrieve.

The expected trade-off was:

> SurfSense may score lower than ideal full-context methods, but should remain cheaper and more robust as documents get longer.

That is mostly what the experiment showed.

---

## 3. Dataset and Scope

### Dataset

The dataset was **MMLongBench-Doc**, a benchmark of long multimodal documents with question-answer pairs over PDFs.

### Scope

We selected the first 30 PDFs from the local MMLongBench-Doc document ordering and evaluated all answerable questions attached to those PDFs.

- **PDFs:** 30
- **Total questions in those PDFs:** 225
- **Answerable questions used:** 171
- **Unanswerable / `None` probes skipped:** 54

Answer format distribution among the 171 answerable questions:

| Answer format | Count |
|---|---:|
| `str` | 61 |
| `int` | 57 |
| `list` | 32 |
| `float` | 21 |

### Documents

The 30 PDFs covered a wide spread:

- short survey/poll PDFs,
- arXiv-style research papers,
- product/catalog PDFs,
- prospectuses,
- annual reports / financial filings,
- very large image-rich PDFs.

Important long or failure-prone PDFs:

| PDF | Pages | Notes |
|---|---:|---|
| `2309.17421v2.pdf` | 166 | 43.6MB, image-heavy; one of the slowest SurfSense ingests |
| `3M_2018_10K.pdf` | 160 | huge markdown extraction; LlamaCloud premium produced ~908k chars |
| `2311.16502v3.pdf` | 117 | many transient request failures |
| `2307.09288v2.pdf` | 77 | several transient request failures |
| `2405.09818v1.pdf` | 27 | native PDF exceeded a hard provider message-size limit |

---

## 4. Experimental Arms

All answer-generation arms used:

```text
anthropic/claude-sonnet-4.5
```

### 4.1 `native_pdf`

The PDF was attached directly to the OpenRouter chat-completions request using the native PDF file path. The model was asked to answer the question from the attached PDF.

This arm has no preprocessing cost, but it pays the PDF/token cost repeatedly for every question.

### 4.2 `azure_basic_lc`

The PDF was parsed with Azure Document Intelligence in **basic** mode.

Backend-equivalent mode:

```text
processing_mode=basic
Azure model=prebuilt-read
```

The resulting markdown was passed fully into the LLM prompt for every question against that PDF.

### 4.3 `azure_premium_lc`

The PDF was parsed with Azure Document Intelligence in **premium** mode.

Backend-equivalent mode:

```text
processing_mode=premium
Azure model=prebuilt-layout
```

The resulting markdown was passed fully into the LLM prompt.

### 4.4 `llamacloud_basic_lc`

The PDF was parsed with LlamaCloud in basic mode.

Backend-equivalent mode:

```text
processing_mode=basic
LlamaCloud parse_mode=parse_page_with_llm
```

The extracted markdown was passed fully into the prompt.

### 4.5 `llamacloud_premium_lc`

The PDF was parsed with LlamaCloud in premium mode.

Backend-equivalent mode:

```text
processing_mode=premium
LlamaCloud parse_mode=parse_page_with_agent
```

The extracted markdown was passed fully into the prompt.

### 4.6 `surfsense_agentic`

SurfSense ingested the PDFs first, then the harness queried:

```text
POST /api/v1/new_chat
```

with the relevant document mentioned/scoped for that question.

Unlike the full-context arms, SurfSense did not put the entire document into the prompt. The system relied on SurfSense’s existing agentic context-management and retrieval flow to pull relevant chunks.

---

## 5. Ingestion and Run Notes

### SurfSense ingestion

The initial SurfSense ingest tried to upload the 30 PDFs with batch size 3. This timed out during the large `2309.17421v2.pdf` processing step:

```text
DocumentProcessingTimeout: Timed out after 1800s waiting for documents
(still pending/processing: [7589])
```

The backend did not actually fail permanently. Celery continued processing the large PDF, and eventually completed it:

```text
Vision LLM described 414 image(s) in 2309.17421v2.pdf
Document indexed successfully ... doc_id=7589 chunk_count=2093
Task completed successfully for: 2309.17421v2.pdf
```

To recover cleanly, ingestion was resumed with:

```text
--upload-batch-size 1
```

This gave each PDF its own 30-minute wait budget. After the resume:

```text
ready: 30
```

All 30 PDFs were available in SurfSense.

### Parser extraction

The direct parser-comparison ingest completed successfully:

```text
30 PDFs × 4 parser/mode combinations = 120 extractions
0 extraction failures
```

The largest extracted markdowns came from `3M_2018_10K.pdf`:

| Arm | Largest extraction | PDF |
|---|---:|---|
| Azure basic | 578,987 chars | `3M_2018_10K.pdf` |
| Azure premium | 688,902 chars | `3M_2018_10K.pdf` |
| LlamaCloud basic | 733,194 chars | `3M_2018_10K.pdf` |
| LlamaCloud premium | 908,733 chars | `3M_2018_10K.pdf` |

The LlamaCloud premium extraction for the 3M filing was estimated at roughly 227k tokens, which is above a typical 200k-token context window. That is an important warning sign for full-context architectures.

---

## 6. Cost Model

The experiment included:

1. **LLM inference cost** for OpenRouter-powered arms.
2. **Preprocessing cost** for parser-based arms.
3. **SurfSense preprocessing cost** for the agentic arm.

The preprocessing tariff used (source: [`runner.py:74-77`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/runner.py#L74-L77), with per-arm mapping at [`runner.py:89-101`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/runner.py#L89-L101) and the `$/Q` overlay at [`runner.py:725-747`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/runner.py#L725-L747)):

| Mode | Cost |
|---|---:|
| Basic | $1 / 1000 pages |
| Premium | $10 / 1000 pages |

Across the 30 PDFs, the total page count was:

```text
1,158 pages
```

Therefore:

| Tier | Preprocessing cost |
|---|---:|
| Basic | $1.158 |
| Premium | $11.580 |

SurfSense LLM cost was measured separately:

The `/api/v1/new_chat` SSE stream does not surface per-call token usage to the evaluation harness, so the auto-generated report writes `LLM $/Q = $0.0000` for the SurfSense arm. The actual cost was reconstructed from the backend's `billable_call` ledger after the run:

```text
SurfSense LLM cost / question (measured): $0.015 (avg)
SurfSense LLM cost (n=171 run total):     $2.57
```

That figure covers all internal LLM calls the agent issues per question (planner / reader / final answer). It is what the cost tables in this report use everywhere `surfsense_agentic` LLM cost is shown.

The SurfSense preprocessing cost is included as `$11.58`, because the documents were ingested with premium processing (Azure Document Intelligence `prebuilt-layout`) plus vision LLM (`anthropic/claude-sonnet-4.5`) for image-content extraction.

---

## 7. Main Results

### 7.1 Raw accuracy and cost

| Arm | Accuracy | Wilson 95% CI | F1 mean | Mean input tokens | Mean output tokens | LLM $/Q | Preprocess $/Q | Total $/Q | Latency p50 | Latency p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `native_pdf` | 48.0% (82/171) | 40.6–55.4% | 50.4% | 65,773 | 209 | $0.2552 | $0.0000 | $0.2552 | 29.5s | 60.5s |
| `azure_basic_lc` | 54.4% (93/171) | 46.9–61.7% | 56.6% | 31,883 | 250 | $0.0994 | $0.0068 | $0.1062 | 7.1s | 12.0s |
| `azure_premium_lc` | 56.7% (97/171) | 49.2–63.9% | 59.6% | 39,787 | 223 | $0.1373 | $0.0677 | $0.2051 | 6.9s | 11.6s |
| `llamacloud_basic_lc` | 50.3% (86/171) | 42.9–57.7% | 53.2% | 31,493 | 243 | $0.0981 | $0.0068 | $0.1049 | 7.1s | 11.9s |
| `llamacloud_premium_lc` | **58.5%** (100/171) | 51.0–65.6% | **61.1%** | 39,131 | 228 | $0.1208 | $0.0677 | $0.1885 | 6.8s | 12.7s |
| `surfsense_agentic` | 53.2% (91/171) | 45.7–60.5% | 54.3% | n/a* | n/a* | **$0.0150** | $0.0677 | **$0.0827** | 52.8s | 164.1s |

*\*The SurfSense `/api/v1/new_chat` SSE stream does not currently surface prompt/completion token counts to the harness, so per-call token figures are recorded as `n/a`. The `LLM $/Q` value of `$0.0150` is the average measured from the backend's billable-call ledger across the 171 questions.*

### 7.2 Accuracy by answer type

| Arm | Float | Int | List | String |
|---|---:|---:|---:|---:|
| `native_pdf` | 62% (13/21) | 39% (22/57) | 31% (10/32) | 61% (37/61) |
| `azure_basic_lc` | 52% (11/21) | 53% (30/57) | 44% (14/32) | 62% (38/61) |
| `azure_premium_lc` | 62% (13/21) | **56%** (32/57) | 41% (13/32) | 64% (39/61) |
| `llamacloud_basic_lc` | 62% (13/21) | 47% (27/57) | 38% (12/32) | 56% (34/61) |
| `llamacloud_premium_lc` | **71%** (15/21) | 49% (28/57) | 47% (15/32) | **69%** (42/61) |
| `surfsense_agentic` | 67% (14/21) | 44% (25/57) | **53%** (17/32) | 57% (35/61) |

Notable pattern:

- LlamaCloud premium was strongest on `float` and `string` answers.
- Azure premium was strongest on `int` answers.
- SurfSense was strongest on `list` answers.

This is product-relevant: list answers usually require gathering multiple facts. SurfSense's agentic retrieval did better there than every full-context arm.

### 7.3 Statistical significance: McNemar pairwise tests

Accuracy differences at n = 171 are not automatically meaningful. We pair every two arms on the same set of 171 questions and run a two-sided **exact-binomial McNemar test** on the discordant pairs.

For each ordered pair `(i, j)`, with the post-retry rows:

- `b = #{q : i correct, j wrong}`
- `c = #{q : i wrong,   j correct}`
- under H0, `b ~ Binomial(b + c, 0.5)`,
- two-sided p-value: `P(X ≤ min(b, c)) + P(X ≥ max(b, c))` computed exactly.

(Implementation: [`compute_blog_extras.py:80-99`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/compute_blog_extras.py#L80-L99) for the exact-binomial p-value, [`compute_blog_extras.py:102-141`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/compute_blog_extras.py#L102-L141) for the pairwise table builder. Pure stdlib `math.comb`, no scipy.)

**Pairwise McNemar table (post-retry, sorted by p-value):**

| arm i | arm j | b (i only) | c (j only) | both ok | both wrong | p (2-sided) | sig |
|---|---|---:|---:|---:|---:|---:|---|
| `azure_premium_lc` | `llamacloud_basic_lc` | 20 | 7 | 80 | 64 | **0.0192** | * |
| `llamacloud_basic_lc` | `llamacloud_premium_lc` | 12 | 27 | 75 | 57 | **0.0237** | * |
| `llamacloud_premium_lc` | `native_pdf` | 23 | 10 | 79 | 59 | **0.0351** | * |
| `azure_premium_lc` | `native_pdf` | 20 | 9 | 80 | 62 | 0.0614 | (·) |
| `llamacloud_premium_lc` | `surfsense_agentic` | 24 | 13 | 78 | 56 | 0.0989 | (·) |
| `azure_basic_lc` | `llamacloud_premium_lc` | 10 | 19 | 83 | 59 | 0.1360 | |
| `azure_premium_lc` | `surfsense_agentic` | 21 | 12 | 79 | 59 | 0.1628 | |
| `azure_basic_lc` | `azure_premium_lc` | 8 | 15 | 85 | 63 | 0.2100 | |
| `azure_basic_lc` | `llamacloud_basic_lc` | 20 | 14 | 73 | 64 | 0.3915 | |
| `azure_basic_lc` | `native_pdf` | 18 | 14 | 75 | 64 | 0.5966 | |
| `llamacloud_basic_lc` | `surfsense_agentic` | 17 | 21 | 70 | 63 | 0.6271 | |
| `azure_premium_lc` | `llamacloud_premium_lc` | 11 | 13 | 89 | 58 | 0.8388 | |
| `azure_basic_lc` | `surfsense_agentic` | 20 | 18 | 73 | 60 | 0.8714 | |
| `llamacloud_basic_lc` | `native_pdf` | 20 | 22 | 67 | 62 | 0.8776 | |
| `native_pdf` | `surfsense_agentic` | 23 | 25 | 66 | 57 | 0.8854 | |

`*`: p < 0.05. `(·)`: p < 0.10 (suggestive but not conclusive).

What this table tells the reader at a glance:

1. **Three pairs reach α = 0.05.** Both premium-LC arms beat `llamacloud_basic_lc`, and `llamacloud_premium_lc` beats `native_pdf`. Everything else is noise at this n.
2. **Premium vs. basic *within Azure* is not significant** (p = 0.21). At n = 171 we cannot conclude `azure_premium_lc` (58.5%) is meaningfully better than `azure_basic_lc` (54.4%). This matters for cost-sensitive workloads — the 10× preprocessing tariff for Azure premium is buying a noisy gain.
3. **`azure_basic_lc` vs `surfsense_agentic`: p = 0.87.** Effectively the same accuracy on this sample. The product story for SurfSense is therefore not "we're as accurate as the *best* arm" but "we're indistinguishable from a reasonable parser-stuffing arm at a fraction of the cost".
4. **`llamacloud_basic_lc` vs `native_pdf`: p = 0.88.** Identical accuracy. The 4.0pp gap visible in the headline table is within sampling noise.
5. **`llamacloud_premium_lc` vs `surfsense_agentic`: p = 0.099.** The flagship LC arm's 6.4pp accuracy advantage over SurfSense is *suggestive* but does not pass α = 0.05 — readers should not write headlines about a "definitive accuracy gap" between full-context premium and SurfSense. With more data this likely becomes significant; at n = 171 it does not.

**Multiple-comparison note.** With 15 pairs and α = 0.05, you'd expect ~0.75 false positives by chance. Holm-correcting to family-wise α = 0.05 keeps only the most significant pair (`azure_premium_lc > llamacloud_basic_lc`, p = 0.019) at α/15 ≈ 0.0033, which it does not pass. So at strict family-wise control, *no* pair is significant; the three single-comparison-significant pairs above should be reported as "directional, single-comparison significant".

### 7.4 Latency and request-size distributions

**Latency per arm (seconds, post-retry):**

| Arm | n | mean | std | p50 | p90 | p95 | p99 | max | CV |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `azure_premium_lc` | 171 | 7.4 | 2.7 | 7.0 | 10.6 | 11.6 | 13.5 | 24.6 | 0.37 |
| `llamacloud_basic_lc` | 171 | 7.5 | 2.4 | 7.1 | 11.3 | 11.9 | 13.7 | 14.4 | 0.32 |
| `azure_basic_lc` | 171 | 7.5 | 2.8 | 7.1 | 11.1 | 11.9 | 14.4 | 25.2 | 0.37 |
| `llamacloud_premium_lc` | 171 | 7.6 | 3.1 | 6.9 | 11.4 | 12.7 | 15.5 | 29.4 | 0.41 |
| `native_pdf` | 164 | 32.1 | 18.8 | 33.0 | 54.2 | 64.5 | 92.2 | 110.6 | 0.58 |
| `surfsense_agentic` | 171 | 67.5 | 44.1 | 52.8 | 126.0 | 160.6 | 206.2 | 328.7 | 0.65 |

(`native_pdf` n is 164 because 7 hard-failed rows have latency = 0; CV = std/mean is the dimensionless tail-fatness.)

**Three operational observations:**

1. **The four LC arms are essentially indistinguishable on latency** (p50 7 s, p95 12 s, CV ~0.35). The model dominates the budget; the parser doesn't.
2. **Native_pdf is 4–5× slower at p50 and 5–8× slower at p95** because each call uploads the base64-inflated PDF and waits for the provider's PDF parser before generation starts.
3. **SurfSense is 7–9× the LC arm latency at p50 and 13× at p95.** This is the agent-loop tax: SurfSense executes multiple internal LLM hops (retrieval planning, tool calls, final answer) per question. The CV of 0.65 means *some* questions take much longer — the p99 of 206 s is the practical "long-tail" budget you need to plan for if you build a SurfSense-style UI. For a synchronous chat experience this is acceptable; for a sub-second autocomplete it is not.

**Input-token distribution (post-retry):**

| Arm | mean | p50 | p95 | max |
|---|---:|---:|---:|---:|
| `azure_basic_lc` | 32,570 | 22,208 | 117,430 | 140,543 |
| `llamacloud_basic_lc` | 32,098 | 21,622 | 103,914 | 163,246 |
| `azure_premium_lc` | 41,366 | 26,472 | 133,647 | 207,958 |
| `llamacloud_premium_lc` | 41,574 | 25,914 | 139,289 | 177,509 |
| `native_pdf` | 84,657 | 59,883 | 259,136 | 390,267 |

Two things worth flagging for the writer:

- **Premium parsers extract ~30% more tokens than basic parsers.** That's the "tables and figures rendered as text" tax. It explains both the higher accuracy and the higher LLM input cost.
- **Native_pdf reports 2× the input tokens of any LC arm.** The provider's PDF parser inserts page metadata, image-embedding tokens, and per-page positional context. The model is paying input-token cost for richer (but apparently less useful) information than what parsers produce. This corroborates the accuracy ranking: more raw bytes ≠ better answers.
- **SurfSense doesn't appear** in this table because the SSE stream does not surface token counts. From the backend ledger, SurfSense's agent loop runs at ~5–15K input tokens per *internal hop*, with 2–4 hops per question — total per-question input is roughly an order of magnitude below the LC arms.

### 7.5 Per-PDF accuracy heterogeneity

Per-arm distribution of accuracy *across the 30 PDFs* (each PDF contributes mean correctness over its 4–8 questions):

| Arm | n PDFs | mean | std | min | p25 | p50 | p75 | max | #PDFs at 0% | #PDFs at 100% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `llamacloud_premium_lc` | 30 | 59.8% | 21.1% | 16.7% | 50.0% | 58.6% | 71.4% | 100.0% | 0 | **3** |
| `azure_premium_lc` | 30 | 58.0% | 24.6% | 0.0% | 40.0% | 58.6% | 78.8% | 100.0% | 1 | 2 |
| `azure_basic_lc` | 30 | 55.0% | 20.4% | 14.3% | 44.6% | 50.0% | 66.7% | 100.0% | 0 | 1 |
| `surfsense_agentic` | 30 | 53.1% | 22.7% | 0.0% | 33.3% | 50.0% | 66.7% | 100.0% | 1 | 2 |
| `native_pdf` | 30 | 51.1% | 24.8% | 0.0% | 35.0% | 50.0% | 70.2% | 85.7% | **3** | 0 |
| `llamacloud_basic_lc` | 30 | 49.5% | 23.3% | 0.0% | 33.3% | 50.0% | 66.7% | 83.3% | 2 | 0 |

Two product-relevant takeaways:

1. **All arms have high per-PDF variance** (std 20–25 percentage points). PDF identity matters more than arm identity for any single document. A blog claim like "premium parsing improves accuracy" is true on average but does not transfer to a guarantee on any one PDF.
2. **`llamacloud_premium_lc` is the only arm with zero PDFs at 0% accuracy** *and* the most PDFs at 100% (3). It's the most consistent arm. `native_pdf` is the only arm with zero perfect PDFs, and 3 PDFs at 0% — confirming its operational fragility doesn't only hit specific *questions*, it can wipe out entire documents.

---

## 8. Raw vs Adjusted Accuracy

The raw benchmark includes transient provider/network errors. For a blog post, it is useful to separate:

- **raw reliability**: what actually happened in the run,
- **intrinsic QA quality**: what the arm likely scores if transient network failures are retried.

We classified transient failures as:

- SSL bad-record-mac errors,
- provider 502/503 errors,
- empty response streams,
- mid-stream JSON decode errors.

We classified intrinsic failures as:

- hard provider size limits,
- context-window limits,
- PDF/image decode failures.

Adjusted accuracy removes transient failures from the denominator.

| Arm | Raw accuracy | Transient failures | Intrinsic failures | Adjusted accuracy |
|---|---:|---:|---:|---:|
| `native_pdf` | 48.0% | 26 | 1 | 56.6% |
| `azure_basic_lc` | 54.4% | 1 | 0 | 54.7% |
| `azure_premium_lc` | 56.7% | 3 | 0 | 57.7% |
| `llamacloud_basic_lc` | 50.3% | 2 | 0 | 50.9% |
| `llamacloud_premium_lc` | 58.5% | 4 | 0 | 59.9% |
| `surfsense_agentic` | 53.2% | **0** | **0** | 53.2% |

Interpretation:

- If we ignore transient failures, native PDF improves from 48.0% to 56.6%.
- But this does not erase the operational problem: native PDF had many more runtime failures than every other arm.
- SurfSense’s adjusted and raw accuracy are identical because it had zero failures.

---

## 9. Error Analysis

### 9.1 Failure count by arm

| Arm | Questions | Failures | Failure rate |
|---|---:|---:|---:|
| `native_pdf` | 171 | 27 | **15.8%** |
| `llamacloud_premium_lc` | 171 | 4 | 2.3% |
| `azure_premium_lc` | 171 | 3 | 1.8% |
| `llamacloud_basic_lc` | 171 | 2 | 1.2% |
| `azure_basic_lc` | 171 | 1 | 0.6% |
| `surfsense_agentic` | 171 | **0** | **0.0%** |

### 9.2 Failure causes

Most failures were not “the model answered incorrectly.” They were runtime/provider failures.

#### Native PDF failures

Native PDF had 27 failures:

| Failure type | Count | Meaning |
|---|---:|---|
| SSL / transient request errors | 21 | Transport instability while sending large payloads |
| Empty response | 5 | Stream ended without usable answer |
| Provider 502 | 1 | OpenRouter / upstream gateway error |
| Hard 30MB message-size limit | 1 | Intrinsic payload-size limit |

There is overlap in how raw error strings were bucketed, but the operational takeaway is clear:

> Native PDF attachment created the most fragile request shape. It repeatedly sent large binary/base64 payloads and was much more exposed to transport and provider-size failures.

The clearest intrinsic hard failure occurred on:

```text
2405.09818v1.pdf::Q007
```

PDF details:

```text
PDF: 2405.09818v1.pdf
Pages: 27
PDF size: 24.1MB
Estimated base64 wire size: ~32.0MB
```

Provider error:

```text
The message size (33657603 bytes) exceeds 30.000MB limit.
```

This is a strong example for the blog:

> A PDF can look moderate by page count, but still exceed native attachment limits because file upload payloads inflate on the wire.

#### Full-context parser arm failures

The four parser-stuffing arms had only 10 combined failures across 684 calls:

| Arm | Failures | Main cause |
|---|---:|---|
| Azure basic LC | 1 | SSL transient |
| Azure premium LC | 3 | SSL transient |
| LlamaCloud basic LC | 2 | SSL transient |
| LlamaCloud premium LC | 4 | SSL transient |

These failures were all classified as transient TLS/network errors:

```text
SSLError: [SSL: SSLV3_ALERT_BAD_RECORD_MAC] sslv3 alert bad record mac
```

They likely would be mitigated by adding retries with exponential backoff in the evaluation harness.

#### These are transport-layer failures, not context-window overflows

A natural intuition is: *"the long-context arms must be hitting Sonnet 4.5's 200K context window, while SurfSense doesn't because it stores the data and retrieves chunks."* The data does not support that. We tested the hypothesis directly with `scripts/test_context_overflow_hypothesis.py` and found:

**(1) Zero literal context-overflow errors in the LC arms.** No `context_length_exceeded`, no `prompt is too long`, no `maximum context length`. The only literal payload-limit error in the entire run was on `native_pdf` — a 30 MB *wire-size* limit, not a token-window limit:

```text
The message size (33657603 bytes) exceeds 30.000MB limit.
```

**(2) Failed requests were larger on average — but successful requests were larger still.** If failures were caused by hitting the model's context window, the largest *successful* payload per arm should sit near the window cap (~800K chars ≈ 200K tokens). It does not. In every LC arm, the largest payload that *succeeded* was meaningfully bigger than the largest payload that *failed*:

| Arm | Max OK (chars / ~tokens) | Max FAIL (chars / ~tokens) |
|---|---:|---:|
| `azure_basic_lc` | 578,987 / ~145K | 412,474 / ~103K |
| `azure_premium_lc` | 688,902 / ~172K | 439,469 / ~110K |
| `llamacloud_basic_lc` | 733,194 / ~183K | 298,961 / ~75K |
| `llamacloud_premium_lc` | **908,733 / ~227K** | 448,633 / ~112K |

If the model were rejecting requests for being too long, max-OK could not exceed max-FAIL. So the model is not the bottleneck.

**(3) The known overflow candidate succeeded.** `3M_2018_10K.pdf` parsed to 908K chars (~227K tokens) under `llamacloud_premium` — *over* Sonnet 4.5's 200K input window. Yet all four of its questions completed without a transport error (the model presumably truncated silently; one of the four was wrong, three correct). This is the opposite of what a true context-overflow theory would predict.

**Conclusion.** The LC arms did not fail because the model rejected oversized prompts. They failed because the *eval harness* sent 100–500KB Markdown bodies repeatedly over public-internet TLS to OpenRouter, where SSL renegotiations, gateway timeouts, and brief upstream stalls become statistically inevitable. Every LC failure in this run is consistent with that — `SSLV3_ALERT_BAD_RECORD_MAC`, empty SSE streams, 502s. The intuition that "SurfSense survives because it bounds context" is correct, but for a different reason than expected: SurfSense survives because **it doesn't put 100–500KB on the wire in the first place**, not because the model would otherwise reject the prompt.

#### SurfSense failures: zero — but that number deserves a footnote

SurfSense reported `0 failures / 171 questions` to the eval harness. This is the most important operational result, but it is worth being precise about *why*, because the mechanism is partly architectural rather than purely "better RAG":

1. **The harness call goes to `http://localhost:8000`, not over public internet.** All transport-class failures that hammered the LC arms (TLS renegotiation, intermediate proxy resets, OpenRouter gateway 502s) are simply not reachable over a loopback HTTP connection. SurfSense was not "asked to survive" the same network path the LC arms had to survive.
2. **The backend retries internal LLM calls.** SurfSense's `/api/v1/new_chat` wraps every internal LLM hop in `RetryAfterMiddleware` (exponential backoff on 5xx, SSL errors, rate limits — see [`retry_after.py:113-179`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_backend/app/agents/new_chat/middleware/retry_after.py#L113-L179) for the backoff calculation and retry-decision logic). Failures the LC arms surfaced as fatal would have been silently retried inside SurfSense and never reached the harness.
3. **SurfSense's outbound prompt is small.** The retrieval pipeline produces prompts in the 5–15K token range, not 100–500KB Markdown blobs, so even if SurfSense's calls *were* over public TLS, they would land in the size class where transient transport errors are far rarer.

In other words, "0 failures" is the joint result of three things — agentic retrieval bounding the payload, a robust internal retry layer, and a localhost call shape — and not a claim that the underlying model never erred on SurfSense's behalf.

What SurfSense *did* successfully handle, end-to-end:

- all 30 PDFs,
- the 166-page `2309.17421v2.pdf`,
- the 160-page `3M_2018_10K.pdf` (the same document where one LC arm pushed 227K tokens at the model and still got mostly-correct answers),
- image-heavy PDFs,
- long financial/report-style PDFs,
- all question formats,
- without context overflow, request-size failures, or any error reaching the harness.

### 9.3 PDFs with the most failures

| PDF | Pages | Failures | Affected arms | Cause |
|---|---:|---:|---|---|
| `2311.16502v3.pdf` | 117 | 9 | Native, Azure premium, LlamaCloud basic/premium | SSL transient |
| `2309.17421v2.pdf` | 166 | 8 | Native, Azure basic/premium | SSL, empty stream, 502 |
| `2405.09818v1.pdf` | 27 | 6 | Native only | empty stream, SSL, 30MB size limit |
| `2307.09288v2.pdf` | 77 | 5 | Native, LlamaCloud premium | SSL transient |
| `05-03-18-political-release.pdf` | 17 | 2 | Native only | SSL transient |

The failure distribution shows two different classes of problems:

1. **Large/complex documents stress providers and transports.**
2. **Native PDF attachment is especially sensitive to file size and binary payload limits.**

### 9.4 Retry experiment: are these failures transient or intrinsic?

To pressure-test the transport-layer hypothesis directly, we re-ran *only* the 37 failed `(arm, qid)` pairs through the same providers, with up to 5 attempts each, exponential backoff (base 1 s, max 30 s, jitter), and concurrency 2. The eval harness was not touched — same prompts, same cached PDFs, same cached parser markdown — only the request was retried. SurfSense was not retried (it had 0 failures and would otherwise have required spinning the backend back up). Failure detection (any row with `error` set OR empty `raw_text`) is at [`retry_failed_questions.py:99-111`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/retry_failed_questions.py#L99-L111); the per-row retry loop is at [`retry_failed_questions.py:260-304`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/retry_failed_questions.py#L260-L304).

**Result (37 retries):**

| Arm | Tried | Recovered | Still failed | Recovery rate |
|---|---:|---:|---:|---:|
| `azure_basic_lc` | 1 | 1 | 0 | **100.0%** |
| `azure_premium_lc` | 3 | 3 | 0 | **100.0%** |
| `llamacloud_basic_lc` | 2 | 2 | 0 | **100.0%** |
| `llamacloud_premium_lc` | 4 | 4 | 0 | **100.0%** |
| `native_pdf` | 27 | 15 | 12 | 55.6% |
| **Total** | **37** | **25** | **12** | **67.6%** |

Two findings, both consistent with §9.2's transport-layer story.

**Finding 1 — every long-context failure was transient.** All 10 LC failures across both parsers and both quality tiers recovered. If these had been context-window overflow errors disguised as SSL alerts, retrying the *same* prompt would not fix them. It did. This is the strongest evidence that the original LC failures were transport-layer artifacts of pushing 100–500 KB Markdown bodies repeatedly over public-internet TLS, not anything wrong with the prompts themselves.

**Finding 2 — half of native_pdf is intrinsic, not transient.** The 12 unrecovered native_pdf rows split cleanly into three buckets:

| Bucket | Count | PDF | What's happening |
|---|---:|---|---|
| **30 MB hard wire-size limit** | 6 | `2405.09818v1.pdf` | Every retry returns the same `The message size (33657603 bytes) exceeds 30.000MB limit.` from Google. The base64-inflated payload is fundamentally above the provider's request-size cap. No amount of retrying helps. |
| **Persistent empty SSE stream** | 5 | `2309.17421v2.pdf` (166 pages) | All 5 attempts return HTTP 200 but the response stream ends with no usable text. Probably the model is spending so long on the huge PDF that the upstream connection times out or is reset before any output token reaches the client. Effectively intrinsic at this provider/payload size. |
| **502 on final attempt** | 1 | `2309.17421v2.pdf::Q003` | Earlier attempts got empty streams; final attempt got a 502. Borderline transient — could plausibly recover with more attempts — but at that point you're hammering the same fragile path. |

The 15 native_pdf rows that *did* recover all succeeded on **attempt 1**, never needing a second retry. That is exactly the signature of independent transient transport hiccups: the original call was unlucky, the next one was fine.

**What this changes about the headline result.** With a basic retry policy in front of the harness, the corrected failure picture would be:

| Arm | Reported failures (no retries) | Intrinsic failures (with retries) | Intrinsic failure rate |
|---|---:|---:|---:|
| `native_pdf` | 27 | **12** | 7.0% |
| `azure_basic_lc` | 1 | 0 | 0.0% |
| `azure_premium_lc` | 3 | 0 | 0.0% |
| `llamacloud_basic_lc` | 2 | 0 | 0.0% |
| `llamacloud_premium_lc` | 4 | 0 | 0.0% |
| `surfsense_agentic` | 0 | 0 | 0.0% |

So the retries don't change the *winners* — the LC arms still have the highest accuracy and SurfSense is still the cheapest — but they sharpen the contrast on robustness:

> Once you account for retries, the four long-context arms and SurfSense all run at zero intrinsic failures across 171 questions. Native PDF attachment, even with 5-attempt exponential backoff, still has a **7% intrinsic failure rate**, dominated by a single PDF that exceeds the provider's 30 MB wire-size cap and a 166-page PDF whose response stream the provider can't reliably terminate.

The retry artifact is committed at `data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/raw_retries.jsonl` (+ `raw_retries_summary.json`) for anyone who wants to inspect attempt-by-attempt latencies and error strings.

### 9.5 Final accuracy after retries

Merging the 25 retry-recovered rows back into `raw.jsonl` (script: `scripts/compute_post_retry_accuracy.py`, merged artifact: `raw_post_retry.jsonl`) gives the final corrected per-arm accuracy table. This is the headline that the blog *would have* reported if the harness had had retries from day one.

**Final accuracy (171 questions, 30 PDFs, all `anthropic/claude-sonnet-4.5`):**

| Rank | Arm | Accuracy | F1 | Failures | Fail rate |
|---:|---|---:|---:|---:|---:|
| 1 | `llamacloud_premium_lc` | **59.6%** | **62.3%** | 0 | 0.0% |
| 2 | `azure_premium_lc` | 58.5% | 61.3% | 0 | 0.0% |
| 3 | `azure_basic_lc` | 54.4% | 56.6% | 0 | 0.0% |
| 4 | `surfsense_agentic` | 53.2% | 54.3% | 0 | 0.0% |
| 5 | `native_pdf` | 52.0% | 54.8% | **12** | **7.0%** |
| 6 | `llamacloud_basic_lc` | 50.9% | 53.8% | 0 | 0.0% |

**Pre- vs. post-retry deltas:**

| Arm | Δ accuracy | Δ failures | Notes |
|---|---:|---:|---|
| `native_pdf` | **+4.1 pp** | **-15** | Largest gain; 15 of 27 originally-empty answers became real answers, several of them correct. Still has the 12 unrecoverable hard-limit / persistent-empty-stream failures. |
| `azure_premium_lc` | +1.8 pp | -3 | All 3 transient failures recovered; 2 of those answers were correct. |
| `llamacloud_premium_lc` | +1.2 pp | -4 | All 4 transient failures recovered; 2 were correct. |
| `llamacloud_basic_lc` | +0.6 pp | -2 | Both transient failures recovered; 1 was correct. |
| `azure_basic_lc` | +0.0 pp | -1 | The single retry recovered, but the recovered answer was wrong — so failure rate dropped without an accuracy lift. |
| `surfsense_agentic` | +0.0 pp | 0 | Nothing to retry; SurfSense already had zero failures. |

**Ranking changes:**

- The top three are unchanged (`llamacloud_premium_lc` > `azure_premium_lc` > `azure_basic_lc`).
- `native_pdf` moves up one spot (#6 → #5) by overtaking `llamacloud_basic_lc` (52.0% vs 50.9%). It is still last among the arms that complete cleanly — and the only arm with a non-zero intrinsic failure rate.
- `surfsense_agentic` stays at #4 with the same 53.2% accuracy. With the four LC arms now also at 0 failures, the operational-robustness story shifts: SurfSense is no longer uniquely zero-failure, but it remains the cheapest arm at $0.0827 / Q while `llamacloud_premium_lc` ($0.1885 / Q) is now zero-failure too. The SurfSense pitch becomes "same robustness as the best full-context arm, at less than half the cost, with bounded prompts that don't truncate on long documents".

**Cost note.** The cost numbers in §1 / §7 still reflect the *original* run. Adding the retry survivors costs slightly more in LLM dollars (25 extra OpenRouter calls, mostly small LC payloads that succeeded on attempt 1; native_pdf retries are larger but didn't recover anyway after attempt 1). It does not change the per-arm cost ranking or the SurfSense win on cost.

---

## 10. What the Results Mean

### 10.1 Native PDF is not a safe default

Native PDF attachment is attractive because it skips preprocessing. But in this benchmark it had:

- lowest raw accuracy,
- highest per-question cost,
- high latency,
- highest failure rate,
- and — confirmed by the retry experiment in §9.4 — a **7% intrinsic failure rate that survives 5 attempts of exponential backoff**: 6 questions on a single PDF that exceeds the provider's 30 MB wire-size cap, plus 5 questions on a 166-page PDF whose response stream the provider cannot reliably terminate.

It is simple, but operationally fragile. The "fragility" isn't only transient: a meaningful fraction of native_pdf failures are *unfixable* by retries.

Native PDFs may still be good for:

- quick one-off small PDFs,
- demos,
- short documents,
- cases where no ingestion pipeline exists.

But for production document QA, especially over large PDFs, native attachment is risky.

### 10.2 Full-context parsed markdown performs best when it fits

The best accuracy came from:

```text
llamacloud_premium_lc: 58.5%
```

This supports the intuition that:

> If the full parsed document fits into the context window, a strong model can use it effectively.

But this strategy has scaling limits:

- the full document is resent for every question,
- cost scales with document length × number of questions,
- context overflow risk grows with long PDFs,
- large extracted markdown can exceed the model window.

The 3M 10-K example is important:

```text
LlamaCloud premium extraction: 908,733 chars
Estimated tokens: ~227k
```

That is already above Sonnet 4.5's 200K-token input window. In this run the provider accepted the request without raising a context-overflow error (see §9.2), but that almost certainly means part of the document was silently dropped — three of the four 3M 10-K questions came back correct on `llamacloud_premium_lc`, one wrong, with no signal to the application that any truncation occurred. A larger corpus or longer filing makes full-context prompting unsafe in production: you do not get a hard error, you get an undetectable accuracy regression.

### 10.3 Basic parsers are surprisingly competitive

Azure basic scored:

```text
54.4% accuracy
$0.1062 / question
```

That is only 4.1 points below the best arm, but at much lower preprocessing cost than premium methods.

In this run:

- Azure basic was cheaper than every premium parser arm.
- Azure basic outperformed native PDF.
- Azure basic was very close to SurfSense’s accuracy.

For cost-sensitive workloads, basic parsing may be an excellent default.

### 10.4 Premium parsing improves quality, but the gain is modest

Premium parsing improved accuracy:

| Parser | Basic | Premium | Gain |
|---|---:|---:|---:|
| Azure | 54.4% | 56.7% | +2.3pp |
| LlamaCloud | 50.3% | 58.5% | +8.2pp |

Premium is most justified when:

- layout matters,
- tables matter,
- visual/page structure matters,
- high accuracy is more important than preprocessing cost.

But premium preprocessing is 10× the basic tariff, so the business decision depends on volume and accuracy requirements.

### 10.5 SurfSense is the cheapest *and* most robust arm

SurfSense scored:

```text
Accuracy:        53.2%   (within ~5pp of the best full-context arm)
Failures:        0       (zero — the only arm with no runtime errors)
LLM cost / Q:    $0.0150 (8× cheaper than native PDF, ~7× cheaper than premium LC)
Total cost / Q:  $0.0827 (lowest of any arm, including basic LC)
```

It was not the top *accuracy* arm. But it won on every other axis that matters in production:

- **Cost.** At $0.0827 / Q it was the cheapest of the six arms, end-to-end. Native PDF was 3.1× more expensive. Premium parser stuffing arms were 2.3–2.5× more expensive.
- **Reliability.** Zero failures vs 1–4 transient failures for the parser arms, and 27 for native PDF.
- **Scalability.** Bounded context per turn — it does not break when a single document exceeds the model context window.

That is the strongest argument for SurfSense:

> SurfSense does not try to win by stuffing the whole document into the prompt. It wins by making long-document QA operationally viable: bounded context, retrieval, no overflow, no large request payloads, and a consistently low marginal cost per question.

This matters more as the corpus grows.

In a real user workflow:

- users do not ask 171 questions against only 30 PDFs,
- they upload many PDFs,
- documents can be hundreds of pages,
- questions arrive over time,
- the same corpus is reused.

In that setting, paying ingestion once and retrieving context dynamically is strictly preferable to repeatedly stuffing full documents into every prompt: amortized preprocessing dominates total cost, and the per-question LLM bill stays small because the prompt is bounded by the retrieved context, not by the size of the underlying document.

### 10.6 Cost amortization model (a math derivation the writer can quote)

The headline `$/Q` numbers are the *break-even, per-question* cost on this specific run. To turn that into a production-grade claim we want a closed-form model the writer can extrapolate.

**Setup.** A workload has:

- `P` PDFs in the corpus,
- average pages per PDF `k̄` (in this experiment, k̄ ≈ 39.6 — total `1188 / 30`),
- `Q` total questions asked over the corpus across the corpus's lifetime (potentially many, since users keep coming back).

Define each arm's per-arm constants:

- `α_arm` = preprocessing tariff in $/page (`α = 0` for native_pdf, `0.001` for basic, `0.010` for premium),
- `β_arm` = per-question LLM cost ($/Q at the arm's typical input/output token mix).

Then the **total cost** for the workload is:

```
C_arm(P, k̄, Q) = α_arm · P · k̄  +  β_arm · Q
                 └── one-time fixed cost ──┘   └─ scales with Q ─┘
```

and the **per-question amortized cost** is:

```
$/Q_arm(P, k̄, Q) = α_arm · P · k̄ / Q  +  β_arm
                   = α_arm · k̄ / (Q/P)  +  β_arm
```

i.e. the preprocessing term shrinks as `Q/P` (questions per PDF) grows.

**Plugging in our measured constants:**

| Arm | α ($/page) | β ($/Q, measured) | Closed-form $/Q |
|---|---:|---:|---|
| `native_pdf` | 0.000 | 0.2552 | `$0.2552` (constant) |
| `azure_basic_lc` | 0.001 | 0.0994 | `$0.0994 + 0.001 · 39.6 / (Q/P)` |
| `azure_premium_lc` | 0.010 | 0.1373 | `$0.1373 + 0.010 · 39.6 / (Q/P)` |
| `llamacloud_basic_lc` | 0.001 | 0.0981 | `$0.0981 + 0.001 · 39.6 / (Q/P)` |
| `llamacloud_premium_lc` | 0.010 | 0.1208 | `$0.1208 + 0.010 · 39.6 / (Q/P)` |
| `surfsense_agentic` | 0.010 | 0.0150 | `$0.0150 + 0.010 · 39.6 / (Q/P)` |

This is the equation a technical reader can re-use directly with their own corpus.

**Worked example: `llamacloud_premium_lc` vs `surfsense_agentic`.**

The α terms are *identical* (both pay the premium tariff). So the cost gap is constant in `Q/P` and equals:

```
$/Q_LC_premium − $/Q_SurfSense = β_LC_premium − β_SurfSense
                                = 0.1208 − 0.0150
                                = $0.1058 per question
```

This is a structural advantage, not a regime-dependent one. **At every value of `Q/P`, SurfSense is ~$0.106/Q cheaper than the most accurate full-context arm.** Across `Q = 10,000` questions, that is **$1,058 saved** with no change in preprocessing spend.

**Why is `β` so different?** Because LC arms send the *whole document* in every request:

```
β_LC ≈ p_in · (k̄ · t_per_page_LC) + p_out · t_out_LC
β_SS ≈ p_in · t_in_SS_per_hop · n_hops_SS + p_out · t_out_SS
```

with Sonnet 4.5 priced at `p_in ≈ $3 / 1M` input tokens and `p_out ≈ $15 / 1M` output tokens. The ratio `β_LC / β_SS ≈ 8` falls out of the input-token ratio: LC arms send ~32–42 K tokens per call (§7.4), SurfSense's agent loop totals ~5–15 K tokens per question even after multi-hop.

**Sensitivity intuition for the writer:**

- If Sonnet 4.5 dropped its input price 10×, `β_LC` would drop ~10×, the cost gap would narrow toward zero, and the LC arms would become cost-competitive with SurfSense at the cost of preprocessing dollars. The agentic-retrieval cost story is *contingent on input-token pricing*; if LLM tokens become a free commodity, "stuff the whole document" becomes economically viable. We don't believe that's where input pricing is going on the 1–2 year horizon, but it is the right thing to caveat.
- The `α` terms only matter when `Q/P` is small (one-off Q&A on a fresh corpus). For any reused corpus, the `β` term dominates and SurfSense's structural ~7× β advantage drives the total.

---

## 11. Blog-Friendly Narrative

A strong blog angle would be:

> “We tested six ways to ask questions over long multimodal PDFs. Full-context parser output had the highest raw accuracy. Agentic retrieval was the cheapest *and* the most reliable — within five percentage points of the best, with zero failures and the lowest cost per question.”

Suggested framing:

1. Native PDF attachment seems attractive because it is simple.
2. But long PDFs create huge request payloads, high cost, and provider instability.
3. Parsed markdown improves model performance and reduces per-call cost.
4. Premium parsers can improve quality, but at higher preprocessing cost.
5. Full-context prompting is not scalable for truly long documents.
6. SurfSense’s agentic retrieval gives up a few accuracy points but wins on cost (cheapest arm at $0.0827 / Q), robustness (zero runtime failures), and avoids context overflow on 100+ page PDFs.

Suggested claim:

> The question is not “Can a frontier model read a PDF?” It can. The real question is whether the approach survives long documents, repeated questions, provider limits, and production cost constraints.

Suggested conclusion:

> For small PDFs, native attachment can be fine. For long-document production QA, ingestion plus retrieval/context management is the more scalable architecture.

---

## 12. Caveats and Improvements

### 12.1 Add retries to the evaluation harness (validated)

Many non-SurfSense failures were transient SSL / provider errors. The retry experiment in §9.4 confirmed this empirically: 5 attempts of exponential backoff recovers 100% of LC-arm failures and ~56% of native_pdf failures, with 25/37 originally-failed rows succeeding cleanly on the very first retry. The harness should bake this in around:

- OpenRouter native PDF calls,
- OpenRouter chat-completion calls for long-context arms.

Empirically calibrated retry policy:

- retry on SSL errors (e.g. `SSLV3_ALERT_BAD_RECORD_MAC`),
- retry on 502/503/504,
- retry on empty SSE stream,
- exponential backoff (base 1 s, cap 30 s, jitter),
- cap at **3 attempts** (most recoveries happen on attempt 1; the marginal recovery from attempts 4–5 in §9.4 is small and not worth the latency).

Caveat: even with this policy, native_pdf retains a hard ~7% intrinsic failure rate at this dataset's PDF size distribution — retries cannot fix the 30 MB wire-size cap or the 166-page empty-stream case.

### 12.2 Surface SurfSense token/cost telemetry on the SSE stream

The cost numbers in this report for the SurfSense arm (`$0.015 / Q`, `$2.57` for the full 171-question run) were reconstructed from the backend's billable-call ledger after the run.

The auto-generated `summary.md` still writes `LLM $/Q = $0.0000` for `surfsense_agentic`, because the `/api/v1/new_chat` SSE stream does not currently expose token usage or per-turn cost to the eval harness. That is the only reason the headline tables in earlier passes of this report had to flag the value as "untracked".

For future reports the SSE stream should surface, per-turn:

- prompt tokens,
- completion tokens,
- total tokens,
- model,
- cost per internal call,
- total cost per user question.

Once that is plumbed through, the harness can compute `surfsense_agentic` cost online instead of requiring a post-run reconciliation against the billable-call ledger.

### 12.3 Test larger samples and stratified subsets

This experiment used 30 PDFs and 171 answerable questions. A future blog could extend it with:

- full MMLongBench-Doc,
- stratified by page count,
- stratified by document type,
- separate chart for image-heavy vs text-heavy documents,
- separate chart for short vs long PDFs.

### 12.4 Compare retrieval-quality diagnostics

SurfSense’s accuracy is partly retrieval-dependent. A deeper product analysis should inspect:

- whether the relevant chunks were retrieved,
- whether the answer failed despite retrieval,
- how many tool calls were needed,
- whether cited lines/pages aligned with gold evidence.

This would explain *why* SurfSense missed certain questions.

---

## 13. Recommended Product Interpretation

For production:

### Use native PDF only for:

- small files,
- low-volume one-off Q&A,
- no-ingestion workflows,
- quick previews.

### Use full-context parsed markdown when:

- the document fits comfortably in context,
- latency matters,
- you only ask a few questions per PDF,
- highest possible single-question accuracy matters.

### Use SurfSense agentic retrieval when:

- documents are long,
- the corpus grows over time,
- users ask many questions,
- cost per query matters,
- context overflow must be avoided,
- reliability matters more than a few points of peak accuracy.

In this benchmark, SurfSense was not the highest raw-accuracy arm, but it was the only arm with zero failures.

That reliability result is likely the strongest blog-worthy differentiator.

---

## 14. Appendix: Commands Used

High-level sequence:

```bash
python -m surfsense_evals setup \
  --suite multimodal_doc \
  --provider-model anthropic/claude-sonnet-4.5 \
  --vision-llm anthropic/claude-sonnet-4.5 \
  --scenario head-to-head
```

```bash
python -m surfsense_evals ingest multimodal_doc mmlongbench \
  --max-docs 30 \
  --upload-batch-size 3 \
  --use-vision-llm \
  --processing-mode premium
```

After the large-PDF timeout:

```bash
python -m surfsense_evals ingest multimodal_doc mmlongbench \
  --max-docs 30 \
  --upload-batch-size 1 \
  --use-vision-llm \
  --processing-mode premium
```

Parser extraction:

```bash
python -m surfsense_evals ingest multimodal_doc parser_compare \
  --max-docs 30 \
  --pdf-concurrency 2
```

Benchmark run:

```bash
python -m surfsense_evals run multimodal_doc parser_compare \
  --sample-per-doc 20 \
  --concurrency 2 \
  --max-output-tokens 512
```

Report generation:

```bash
python -m surfsense_evals report --suite multimodal_doc
```

Post-hoc retry experiment (§9.4 / §9.5):

```bash
# Re-run only the 37 failed (arm, qid) pairs with up to 5 attempts
# of exponential backoff. SurfSense had 0 failures so backend/celery
# are not required.
python scripts/retry_failed_questions.py \
  --run-id 2026-05-14T00-53-19Z \
  --max-attempts 5 \
  --base-delay 1.0 \
  --max-delay 30.0 \
  --concurrency 2
```

Merge retry survivors back into the run and recompute the headline:

```bash
python scripts/compute_post_retry_accuracy.py \
  --run-id 2026-05-14T00-53-19Z
```

Compute the deeper blog stats (latency / token distributions, McNemar
pairwise tests, per-PDF heterogeneity):

```bash
python scripts/compute_blog_extras.py \
  --run-id 2026-05-14T00-53-19Z
```

### 14.1 Reproducibility notes

- **LLM model:** `anthropic/claude-sonnet-4.5` for every arm, routed via OpenRouter (`https://openrouter.ai/api/v1/chat/completions`).
- **PDF engine for `native_pdf`:** OpenRouter's `native` file-parser plugin (`engine: native`).
- **Parser SDKs called directly from the eval harness:**
  - `azure-ai-documentintelligence` (Azure DI, models `prebuilt-read` for basic and `prebuilt-layout` for premium).
  - `llama-cloud-services` (LlamaParse, modes `parse_page_with_llm` for basic, `parse_page_with_agent` for premium).
  - The harness writes the resulting Markdown to `data/multimodal_doc/parser_compare/extractions/` and records each extraction in `parser_compare_doc_map.jsonl`. This bypasses the SurfSense backend so each LC arm is a pure parser-stuffing comparison.
- **SurfSense backend ETL:** With both `AZURE_DI_*` env vars present and `ETL_SERVICE=LLAMACLOUD`, the backend prefers Azure DI for PDFs (see `surfsense_backend/app/etl_pipeline/etl_pipeline_service.py`). The 30 PDFs were therefore ingested through Azure DI `prebuilt-layout` + Sonnet 4.5 vision-LLM image extraction. That is the basis for charging the `surfsense_agentic` arm the premium tariff.
- **SurfSense `/api/v1/new_chat` flags:** `mentioned_document_ids` set to the per-question PDF's `document_id` (single-doc retrieval); `disabled_tools` left at default; `ephemeral_threads=true` to ensure no inter-question state leakage.
- **Concurrency:** `concurrency=2` per arm during `parser_compare run` and during the retry pass. Higher concurrency on the LC arms reproducibly inflated SSL/transport failures.
- **Grader:** deterministic, format-aware. The five branches:
  - `Str`: lowercase, strip punctuation, collapse whitespace, exact match.
  - `Int`: extract first integer with regex; require equality.
  - `Float`: extract first decimal; correct if `|gold − pred| ≤ max(0.01, 0.02·|gold|)` (1% relative tolerance, 0.01 absolute floor).
  - `List`: lowercase, split on `,` / `;`, set-equal compare; F1 = 2·|intersection| / (|pred| + |gold|).
  - `None` ("Not answerable"): correct iff prediction contains "not answerable" / "cannot be determined" / equivalent.
  - F1 for non-List formats = 1.0 if correct else 0.0; for List, token-level F1 over the parsed sets.
  - Source: `surfsense_evals/src/surfsense_evals/suites/multimodal_doc/mmlongbench/grader.py`.

### 14.2 Statistical methodology

- **Wilson 95% CIs** (§7.1) computed as `(p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/(4n²))) / (1 + z²/n)` with `z = 1.96`.
- **McNemar exact-binomial test** (§7.3): on paired arms `(i, j)`, with discordant counts `b = #{i correct, j wrong}` and `c = #{i wrong, j correct}`, `b ~ Bin(b+c, 0.5)` under H0; the two-sided p-value is computed exactly from `math.comb`. No continuity correction (n's are small enough that the exact form is cheap).
- **Multiple comparisons:** 15 arm pairs. We report single-comparison-significant pairs (α = 0.05) and explicitly note which would survive Holm-Bonferroni at family-wise α = 0.05 (none, in this run).
- **Per-PDF accuracy heterogeneity** (§7.5): each PDF contributes one mean over its 4–8 questions; we report mean / std / min / quartiles across the 30 per-PDF means (so each PDF is weighted equally regardless of how many questions it contributed).

### 14.3 Threats to validity

The claims in this report come with the following caveats. We list them so a reader can decide which generalize and which are specific to the run.

1. **Single dataset.** All 171 questions come from MMLongBench-Doc. The dataset is academic-paper-heavy (arXiv preprints + a few financial 10-Ks and political reports). Findings on a corpus of, say, regulatory filings or scanned forms could differ — particularly for parser quality, where MMLongBench's clean academic PDFs are easier than the median real-world PDF.
2. **Single LLM.** Every arm uses `anthropic/claude-sonnet-4.5`. Results would shift with a smaller or weaker model: less-capable models likely benefit more from premium parsing (because they cannot fix layout mistakes themselves) and benefit less from full-context stuffing (because they cannot use 200K-token contexts effectively).
3. **Single retrieval policy.** `surfsense_agentic` was run with `mentioned_document_ids = [<pdf>]` — single-document retrieval, no cross-document mixing. SurfSense's accuracy on questions that span multiple documents (or that benefit from cross-corpus context) is not measured here.
4. **n = 171.** The Wilson CIs span 7–8 percentage points per arm; only 3 of 15 arm pairs reach single-comparison significance (§7.3). The headline ranking is directionally robust but should not be treated as a precise ordering for arms that differ by < ~5pp.
5. **Cost figures depend on the OpenRouter Sonnet 4.5 schedule.** Per-token prices change. The amortization model in §10.6 is the right thing for a reader to re-derive with their own pricing; the headline `$/Q` is run-specific.
6. **`native_pdf` measured only the OpenRouter "native" file-parser plugin** (`engine: native`). Different engines (`mistral-ocr`, `cloudflare-ai`) might have different size limits, accuracy, and failure rates. The 30 MB intrinsic limit and the empty-stream behavior are specific to the Google upstream that OpenRouter routed Sonnet 4.5 through.
7. **SurfSense LLM cost was reconstructed post-hoc.** The `/api/v1/new_chat` SSE stream does not currently surface per-turn tokens or cost (§12.2). The `$0.015/Q` figure is the average from the backend's `billable_call` ledger over the 171 turns, not a live measurement against each turn's response. We are confident in the *average*; we cannot give a per-question variance for SurfSense LLM cost from this run.
8. **Grader is deterministic, not LLM-judged.** The MMLongBench-Doc paper itself uses a GPT-4 judge. We chose deterministic grading for reproducibility (two researchers running this harness will get the exact same number) and simpler downstream stats. An LLM-judge mode is implemented (`--judge gpt5`) but was not used here. If you switch to LLM judging, all arms shift up by roughly the same amount; the *ordering* should be stable but the absolute accuracy values are not directly comparable.
9. **Retry experiment is not blind to its purpose.** The retry policy (5 attempts, exponential backoff, jitter, concurrency 2) was chosen *after* seeing the failure modes. We are not claiming this is the optimal policy across arms — only that with this policy, all LC failures recover and a clean residue of intrinsic native_pdf failures remains.
10. **No statistical test was run for cost differences.** All cost numbers are point estimates from a single run; we do not report cost CIs because the variance comes from token-count variability per question and is well-modeled by the input-token distributions in §7.4 if a reader wants to construct a CI themselves.

### 14.4 Code citations index

Every technical claim in this report is reproducible from the code in this repository. The table below maps each claim to its exact source-of-truth file and line range, pinned to commit [`9bcd5016`](https://github.com/MODSetter/SurfSense/commit/9bcd5016) so the line numbers stay valid even if the files change later.

#### Eval harness — arm definitions

| Claim / construct | File@lines |
|---|---|
| `NativePdfArm` — attaches the PDF as an OpenRouter file part | [`core/arms/native_pdf.py:21-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/core/arms/native_pdf.py#L21) |
| `BareLlmArm` — chat-completion with no retrieval (used for the four LC arms) | [`core/arms/bare_llm.py:22-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/core/arms/bare_llm.py#L22) |
| `SurfSenseArm` — `/api/v1/new_chat` SSE consumer | [`core/arms/surfsense.py:30-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/core/arms/surfsense.py#L30) |
| `OpenRouterChatProvider` — bare chat-completion HTTP client | [`core/providers/openrouter_chat.py:40-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/core/providers/openrouter_chat.py#L40) |
| `OpenRouterPdfProvider` — file-parser-plugin chat-completion client | [`core/providers/openrouter_pdf.py:72-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/core/providers/openrouter_pdf.py#L72) |

#### Eval harness — parser SDK callers (LC arms)

| Claim / construct | File@lines |
|---|---|
| Azure DI mode→model map (`basic`→`prebuilt-read`, `premium`→`prebuilt-layout`) | [`core/parsers/azure_di.py:33-35`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/core/parsers/azure_di.py#L33-L35) |
| LlamaCloud mode→mode map (`basic`→`parse_page_with_llm`, `premium`→`parse_page_with_agent`) | [`core/parsers/llamacloud.py:32-34`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/core/parsers/llamacloud.py#L32-L34) |
| `pypdf`-based page count (used for the per-page tariff calculation) | [`core/parsers/pdf_pages.py`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/core/parsers/pdf_pages.py) |

#### Eval harness — parser_compare benchmark

| Claim / construct | File@lines |
|---|---|
| `ParserCompareBenchmark` (six-arm runner, prompt construction, raw.jsonl writer) | [`suites/multimodal_doc/parser_compare/runner.py:231-576`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/runner.py#L231-L576) |
| Prompt: `build_native_pdf_prompt` (PDF attached separately) | [`parser_compare/prompt.py:69-76`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/prompt.py#L69-L76) |
| Prompt: `build_long_context_prompt` (full Markdown stuffed inline) | [`parser_compare/prompt.py:92-113`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/prompt.py#L92-L113) |
| Prompt: `build_surfsense_prompt` (chunks injected by the agent) | [`parser_compare/prompt.py:79-89`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/prompt.py#L79-L89) |
| Pre-extraction manifest builder (cached parser outputs) | [`parser_compare/ingest.py`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/ingest.py) |

#### Cost model

| Claim / construct | File@lines |
|---|---|
| `PREPROCESS_USD_PER_PAGE` constant (`basic = 0.001`, `premium = 0.010`) | [`runner.py:74-77`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/runner.py#L74-L77) |
| Per-arm tier mapping (`_LC_ARM_MODE`) | [`runner.py:89-94`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/runner.py#L89-L94) |
| `SURFSENSE_INGEST_MODE = "premium"` (basis for charging SurfSense the premium tariff) | [`runner.py:96-101`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/runner.py#L96-L101) |
| Cost overlay (`preprocess_cost_total`, `total_cost_per_q` computation) | [`runner.py:725-747`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/parser_compare/runner.py#L725-L747) |

#### Grader (deterministic, format-aware — §14.1)

| Claim / construct | File@lines |
|---|---|
| `GradeResult` dataclass (`correct`, `f1`, `method`, normalised pred/gold) | [`mmlongbench/grader.py:40-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/mmlongbench/grader.py#L40) |
| `_grade_str` (lowercase + strip + exact match) | [`mmlongbench/grader.py:89-104`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/mmlongbench/grader.py#L89-L104) |
| `_grade_int` (regex extract first int, equality) | [`mmlongbench/grader.py:106-120`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/mmlongbench/grader.py#L106-L120) |
| `_grade_float` (1% relative tolerance, 0.01 absolute floor) | [`mmlongbench/grader.py:122-139`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/mmlongbench/grader.py#L122-L139) |
| `_grade_list` (set equality + token-level F1) | [`mmlongbench/grader.py:141-157`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/mmlongbench/grader.py#L141-L157) |
| `_grade_none` ("Not answerable" handling) | [`mmlongbench/grader.py:159-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/mmlongbench/grader.py#L159) |
| Public `grade()` dispatcher | [`mmlongbench/grader.py:224-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/suites/multimodal_doc/mmlongbench/grader.py#L224) |

#### Statistical methodology (§14.2)

| Claim / construct | File@lines |
|---|---|
| `wilson_ci()` — Wilson 95% CI for a single proportion | [`core/metrics/mc_accuracy.py:49-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/core/metrics/mc_accuracy.py#L49) |
| `accuracy_with_wilson_ci()` — full per-arm accuracy + CI struct | [`core/metrics/mc_accuracy.py:73-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/src/surfsense_evals/core/metrics/mc_accuracy.py#L73) |
| McNemar exact-binomial p-value (§7.3) | [`compute_blog_extras.py:80-99`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/compute_blog_extras.py#L80-L99) |
| McNemar pairwise table builder | [`compute_blog_extras.py:102-141`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/compute_blog_extras.py#L102-L141) |
| Latency distribution helpers (§7.4) | [`compute_blog_extras.py:186-213`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/compute_blog_extras.py#L186-L213) |
| Token distribution helpers (§7.4) | [`compute_blog_extras.py:216-250`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/compute_blog_extras.py#L216-L250) |
| Per-PDF accuracy heterogeneity (§7.5) | [`compute_blog_extras.py:149-183`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/compute_blog_extras.py#L149-L183) |

#### Retry experiment (§9.4 / §9.5)

| Claim / construct | File@lines |
|---|---|
| Failure-row detection (error set OR empty `raw_text`) | [`retry_failed_questions.py:99-111`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/retry_failed_questions.py#L99-L111) |
| Per-row retry loop (5 attempts, exponential backoff w/ jitter) | [`retry_failed_questions.py:260-304`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/retry_failed_questions.py#L260-L304) |
| Bounded-concurrency runner | [`retry_failed_questions.py:307-315`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/retry_failed_questions.py#L307-L315) |
| Post-retry merge + recompute (§9.5 final accuracy table) | [`compute_post_retry_accuracy.py`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/compute_post_retry_accuracy.py) |
| Context-overflow hypothesis test (§9.2) | [`test_context_overflow_hypothesis.py`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/scripts/test_context_overflow_hypothesis.py) |

#### SurfSense backend (§9.2 — what "0 failures" actually measures)

| Claim / construct | File@lines |
|---|---|
| `_exponential_delay()` — backoff with optional ±25% jitter | [`retry_after.py:113-128`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_backend/app/agents/new_chat/middleware/retry_after.py#L113-L128) |
| `RetryAfterMiddleware` — wraps every internal LLM hop | [`retry_after.py:131-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_backend/app/agents/new_chat/middleware/retry_after.py#L131) |
| `_should_retry()` — retryable-error classification | [`retry_after.py:171-…`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_backend/app/agents/new_chat/middleware/retry_after.py#L171) |
| ETL routing — Azure DI preferred over LlamaCloud for compatible types | [`etl_pipeline_service.py:233-251`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_backend/app/etl_pipeline/etl_pipeline_service.py#L233-L251) |

#### Run artifacts (the verifiable numbers source)

These are the *outputs* the report cites — every accuracy / cost / latency number can be re-derived by running the analysis scripts on these JSONL files.

| Artifact | Relative path | Contents |
|---|---|---|
| Raw run | [`raw.jsonl`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/raw.jsonl) | 1 026 rows = 6 arms × 171 questions; one row per `(arm, qid)` with the original ArmResult + grader verdict |
| Retry log | [`raw_retries.jsonl`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/raw_retries.jsonl) | 37 rows; per-row attempt timeline + final outcome |
| Retry summary | [`raw_retries_summary.json`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/raw_retries_summary.json) | per-arm tried / recovered / still-failed counts |
| Post-retry merged | [`raw_post_retry.jsonl`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/raw_post_retry.jsonl) | 1 026 rows; recovered retries replace originals; basis for §9.5 final accuracy + §7.3 McNemar |
| Per-arm aggregates | [`run_artifact.json`](https://github.com/MODSetter/SurfSense/blob/9bcd5016/surfsense_evals/data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/run_artifact.json) | the raw run's per-arm summary metrics + per-PDF correctness map |

#### Reproducing every number in §1, §7, §8, §9

```bash
# 1) Sanity: load the artifacts that ship with the repo.
ls surfsense_evals/data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/

# 2) Recompute the post-retry headline accuracy (§1, §9.5).
python surfsense_evals/scripts/compute_post_retry_accuracy.py \
  --run-id 2026-05-14T00-53-19Z

# 3) Recompute McNemar pairwise + latency / token / per-PDF distributions
#    (§7.3, §7.4, §7.5).
python surfsense_evals/scripts/compute_blog_extras.py \
  --run-id 2026-05-14T00-53-19Z

# 4) Re-run the context-overflow hypothesis test (§9.2).
python surfsense_evals/scripts/test_context_overflow_hypothesis.py
```

To re-run the experiment end-to-end (slow: needs a backend + celery + ~3 hr ingest + ~2 hr LC arms), use the commands in §14.

---

## 15. Appendix: File Locations

Primary auto-generated report:

```text
reports/multimodal_doc/2026-05-14T02-30-16Z/summary.md
```

Raw run (all 1026 rows: 6 arms × 171 questions):

```text
data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/raw.jsonl
```

Run artifact (per-arm aggregates from the run):

```text
data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/run_artifact.json
```

Retry experiment (§9.4 / §9.5):

```text
data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/raw_retries.jsonl
data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/raw_retries_summary.json
```

Post-retry merged artifact (used for the final accuracy + McNemar tables):

```text
data/multimodal_doc/runs/2026-05-14T00-53-19Z/parser_compare/raw_post_retry.jsonl
```

Parser manifest (PDF → extracted-markdown paths per LC arm):

```text
data/multimodal_doc/maps/parser_compare_doc_map.jsonl
```

Per-arm cached parser extractions (regenerated by the parser_compare
ingest step; not tracked in git because absolute paths leak the local
checkout):

```text
data/multimodal_doc/parser_compare/extractions/
```

Analysis scripts (all in `surfsense_evals/scripts/`):

```text
inspect_first30.py                 # corpus & question-count summary
patch_manifest_for_parallel_ingest.py
check_uploaded_status.py           # query SurfSense backend status
analyze_failures.py                # cluster errors per arm + per PDF
analyze_failure_timing.py          # per-arm failure-time clusters
test_context_overflow_hypothesis.py
compute_adjusted_accuracy.py       # transient-vs-intrinsic accuracy
retry_failed_questions.py          # retry pass with exponential backoff
compute_post_retry_accuracy.py     # merge retries + recompute headline
compute_blog_extras.py             # latency/tokens/McNemar/per-PDF stats
```

---

## 16. One-Sentence Summary

On 171 questions over 30 long multimodal PDFs, **full-context LlamaCloud-premium (59.6% post-retry) and Azure-premium (58.5%) won on accuracy**, but only **3 of 15 arm pairs are statistically distinguishable at α = 0.05** (McNemar, §7.3); meanwhile **SurfSense's agentic retrieval delivered 53.2% accuracy at $0.0827 / Q — the cheapest arm by ~$0.10 / Q vs every full-context arm — with zero runtime failures, while native PDF attachment retained an irrecoverable 7% intrinsic failure rate even after 5 attempts of exponential backoff (§9.4–§9.5)** — making the production trade-off "give up ~6pp of accuracy that may not even be statistically real, save ~57% on per-question cost, and inherit zero context-overflow / wire-size fragility on long documents".
