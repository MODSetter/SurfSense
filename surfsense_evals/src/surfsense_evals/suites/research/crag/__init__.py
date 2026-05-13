"""CRAG — Comprehensive RAG Benchmark (Yang et al., Meta, KDD Cup 2024).

Source: https://github.com/facebookresearch/CRAG  (Tasks 1, 2, and 3)
Paper:  https://arxiv.org/abs/2406.04744

This package registers two siblings:

* ``crag``    — Tasks 1 & 2: 5 candidate pages per question.
* ``crag_t3`` — Task 3:       50 candidate pages per question. The
  long-context arm is capped to the top-5 (the realistic "naive
  RAG = pick top-K results" baseline); SurfSense retrieves over
  all 50, where its rerank becomes the entire contribution.

Both share the grader, prompt, runner, and report code; only the
ingest path differs (single bz2 vs 4-part tar.bz2 streamed).

CRAG ships ~2,706 factual QA pairs, each paired with **5 full HTML
pages** retrieved as the top-5 of a real web search at ``query_time``
(50 in Task 3).
The benchmark spans 5 domains (finance, music, movie, sports, open)
and 8 question types (simple, comparison, aggregation, set, multi-hop,
post-processing, false_premise, simple_w_condition) — heads/torsos/
tails of entity popularity — and an explicit static→real-time
freshness axis.

Why CRAG demonstrates SurfSense more clearly than FRAMES
--------------------------------------------------------
FRAMES tested SurfSense vs. *no retrieval at all* — a fair "naive
prompting" baseline (the published 40.8% number) but not a competing
RAG product. CRAG enables a three-way comparison:

* ``bare_llm``      — chat completion with the question only. CRAG
  paper: ≤34% accuracy ("LLM cold").
* ``long_context``  — stuff all 5 extracted page texts straight into
  the prompt (the "naive RAG" / "straightforward RAG" arm in the
  paper). Published baseline: ~44%.
* ``surfsense``     — POST ``/api/v1/new_chat`` with retrieval scoped
  to the question's 5 ingested pages (``mentioned_document_ids``).

So the headline becomes "SurfSense vs. context-stuffed long-context
LLM, both fed the same 5 pages" — a head-to-head against the simplest
realistic RAG strategy, not against an unarmed model.

Scoring follows the CRAG paper: each prediction is graded as
**correct** (+1), **missing/I-don't-know** (0), or **incorrect** (-1),
and the headline metric is the *Truthfulness Score*:
``(#correct - #incorrect) / total`` — penalising hallucinations
relative to refusals.
"""

from __future__ import annotations

from ....core import registry as _registry
from .runner import CragBenchmark, CragTask3Benchmark

_registry.register(CragBenchmark())
_registry.register(CragTask3Benchmark())
