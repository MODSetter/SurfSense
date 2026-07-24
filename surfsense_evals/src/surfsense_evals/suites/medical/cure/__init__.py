"""CUREv1 — secondary single-arm SurfSense retrieval measurement.

Source: https://huggingface.co/datasets/clinia/CUREv1
Paper: https://arxiv.org/html/2412.06954v4

Pure retrieval benchmark — 10 medical disciplines, English/French/Spanish
queries, expert-curated qrels (graded 0/1/2). The harness ingests the
corpus, runs each query via SurfSense's ``/api/v1/new_chat``, parses
chunk citations, maps them back to CUREv1 ``corpus-id``, and scores
Recall@k / MRR / nDCG@10 against qrels.
"""

from __future__ import annotations

from ....core import registry as _registry
from .runner import CureBenchmark

_registry.register(CureBenchmark())
