"""MMLongBench-Doc — head-to-head Native PDF (vision) vs SurfSense (vision RAG).

Source: https://huggingface.co/datasets/yubo2333/MMLongBench-Doc
Paper:  https://arxiv.org/abs/2407.01523 (NeurIPS 2024 D&B Track)

* 135 long PDFs (avg 47 pages, multi-modal: text, images, charts, tables)
* 1,091 expert-annotated questions
* 33% require evidence from multiple pages
* ~22% intentionally unanswerable (tests hallucination resistance)
* 7 document types: research report, tutorial/workshop, academic paper,
  financial report, brochure, government, manuals
"""

from __future__ import annotations

from ....core import registry as _registry
from .runner import MMLongBenchDocBenchmark

_registry.register(MMLongBenchDocBenchmark())
