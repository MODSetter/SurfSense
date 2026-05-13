"""FRAMES — multi-hop Wikipedia retrieval & reasoning (google/frames-benchmark).

Source: https://huggingface.co/datasets/google/frames-benchmark
Paper:  https://arxiv.org/abs/2409.12941 (Krishna et al., 2024)

* 824 multi-hop questions, each requiring 2-15 Wikipedia articles
* 5 reasoning types: numerical, tabular, multiple constraints,
  temporal, post-processing
* Published Gemini-Pro-1.5 baselines:
  - Naive prompting (no retrieval):    40.8%
  - BM25, top-4:                       47.4%
  - Multi-step retrieval & reasoning:  66.0%
  - Oracle retrieval (gold articles):  72.9%

This is the benchmark that *finally* puts SurfSense's strongest claim
on trial: cross-document iterative retrieval. The harness ingests
every Wikipedia article referenced by any question in the run sample
into a single SearchSpace; SurfSense answers without
``mentioned_document_ids`` so its agent has to actually retrieve.
The bare-LLM arm answers from the prompt only (the published 40.8%
baseline number).
"""

from __future__ import annotations

from ....core import registry as _registry
from .runner import FramesBenchmark

_registry.register(FramesBenchmark())
