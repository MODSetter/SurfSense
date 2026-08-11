"""Installed artifact-verification format adapters."""

from __future__ import annotations

from pathlib import PurePosixPath

from .base import FormatAdapter
from .docx import check_docx
from .pdf import check_pdf

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_ADAPTERS = {
    ".pdf": FormatAdapter(
        name="pdf",
        suffix=".pdf",
        mime_type=PDF_MIME,
        convert_to_pdf=False,
        check=check_pdf,
    ),
    ".docx": FormatAdapter(
        name="docx",
        suffix=".docx",
        mime_type=DOCX_MIME,
        convert_to_pdf=True,
        check=check_docx,
    ),
}


def get_format_adapter(path: str) -> FormatAdapter:
    suffix = PurePosixPath(path).suffix.lower()
    try:
        return _ADAPTERS[suffix]
    except KeyError:
        raise ValueError(
            f"Artifact verification does not support {suffix or 'this file'}"
        ) from None
