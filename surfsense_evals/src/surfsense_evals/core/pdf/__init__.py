"""Domain-agnostic PDF rendering helper. Lazy import."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .render import (
        PdfImage,
        render_pdf,
        render_pdf_with_images,
        render_text_files_to_pdf,
    )

__all__ = [
    "PdfImage",
    "render_pdf",
    "render_pdf_with_images",
    "render_text_files_to_pdf",
]


_LAZY = {"PdfImage", "render_pdf", "render_pdf_with_images", "render_text_files_to_pdf"}


def __getattr__(name: str):
    if name in _LAZY:
        from . import render as _mod

        return getattr(_mod, name)
    raise AttributeError(f"module 'surfsense_evals.core.pdf' has no attribute {name!r}")
