"""Research / multi-document RAG benchmarks.

Distinct from ``multimodal_doc`` (PDF-bound) and ``medical`` (one
question = one source PDF). Benchmarks here put *retrieval and
reasoning across many documents* in the critical path — the regime
where SurfSense's chunk-level RAG should shine versus "pour the
entire document into the LLM" or "ask the LLM cold".

* ``frames`` (google/frames-benchmark) — 824 multi-hop Wikipedia
  questions; tests bare-LLM vs SurfSense over a shared ~330-doc
  corpus.
* ``crag``   (facebookresearch/CRAG, KDD Cup 2024) — 2,706 web QA
  pairs with 5 pre-retrieved HTML pages each; tests bare-LLM vs
  long-context-stuffed LLM vs SurfSense over the question's 5
  scoped pages — the closest comparison to a competing RAG product.
"""

from __future__ import annotations
