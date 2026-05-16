"""CRAG — Comprehensive RAG Benchmark (Yang et al., Meta, KDD Cup 2024).

Source: https://github.com/facebookresearch/CRAG (Tasks 1 & 2)
Paper:  https://arxiv.org/abs/2406.04744

CRAG ships ~2,706 factual QA pairs, each paired with **5 full HTML
pages** retrieved as the top-5 of a real web search at ``query_time``.
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
from .runner import CragBenchmark

_registry.register(CragBenchmark())
