"""Multimodal long-document benchmarks (PDFs with embedded images/charts/tables).

Distinct from the medical suite because these documents are domain-mixed
(research reports, financials, manuals, government, brochures, papers).
The hypothesis being tested here is *general*: does SurfSense's
chunking-based vision RAG preserve information that lives in pixels —
across long PDFs, across pages — versus feeding the same PDF directly
to a vision-capable model?

Subpackages register themselves with ``core.registry`` on import. The
``suites/__init__.py`` discovery walker imports them automatically.
"""

from __future__ import annotations
