"""Installed artifact-verification format adapters."""

from __future__ import annotations

from pathlib import PurePosixPath

from .base import FormatAdapter
from .docx import check_docx
from .pdf import check_pdf
from .pptx import check_pptx
from .video import check_video, reject_buffered_video_check
from .xlsx import check_xlsx

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MP4_MIME = "video/mp4"

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
    ".pptx": FormatAdapter(
        name="pptx",
        suffix=".pptx",
        mime_type=PPTX_MIME,
        convert_to_pdf=True,
        check=check_pptx,
        rendered_min_chars=0,
        expects_exact_page_count=True,
        review_kind="slides",
    ),
    ".xlsx": FormatAdapter(
        name="xlsx",
        suffix=".xlsx",
        mime_type=XLSX_MIME,
        convert_to_pdf=False,
        check=check_xlsx,
        requires_visual_review=False,
    ),
    ".mp4": FormatAdapter(
        name="video",
        suffix=".mp4",
        mime_type=MP4_MIME,
        convert_to_pdf=False,
        check=reject_buffered_video_check,
        requires_visual_review=False,
        sandbox_check=check_video,
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
