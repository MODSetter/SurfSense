"""Tiny pypdf wrapper for "how many pages does this PDF have?".

Used by ``parser_compare`` to:

* Decide LlamaCloud's per-page job timeout.
* Compute the SurfSense preprocessing dollar cost
  (``$1 / 1k pages`` for basic, ``$10 / 1k pages`` for premium) so the
  report can show "ingest + LLM" total cost per arm.

Returns ``0`` (and logs) on parse failure rather than raising — costs
shown as ``?`` are always better than a benchmark that crashes mid-run.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def count_pdf_pages(path: Path) -> int:
    """Return the page count for ``path``; ``0`` if pypdf can't open it."""

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to count pages for %s: %s", path, exc)
        return 0


__all__ = ["count_pdf_pages"]
