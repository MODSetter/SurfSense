"""Installed artifact-verification format adapters."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from .base import FormatAdapter
from .docx import check_docx
from .flashcards import check_flashcards_json, flashcards_to_markdown
from .html import check_html
from .infographic import check_infographic_markdown, check_infographic_png
from .mindmap import check_mindmap_markdown, check_mindmap_png
from .pdf import check_pdf
from .pptx import check_pptx
from .quiz import check_quiz_json, quiz_to_markdown
from .video import check_video, reject_buffered_video_check
from .xlsx import check_xlsx

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HTML_MIME = "text/html"
MP4_MIME = "video/mp4"
PNG_MIME = "image/png"
VerifiableArtifactFormat = Literal[
    "pdf",
    "docx",
    "pptx",
    "xlsx",
    "html",
    "video",
    "mindmap",
    "infographic",
    "flashcards",
    "quiz",
]

_ADAPTERS = {
    "pdf": FormatAdapter(
        name="pdf",
        suffix=".pdf",
        mime_type=PDF_MIME,
        convert_to_pdf=False,
        check=check_pdf,
    ),
    "docx": FormatAdapter(
        name="docx",
        suffix=".docx",
        mime_type=DOCX_MIME,
        convert_to_pdf=True,
        check=check_docx,
    ),
    "pptx": FormatAdapter(
        name="pptx",
        suffix=".pptx",
        mime_type=PPTX_MIME,
        convert_to_pdf=True,
        check=check_pptx,
        rendered_min_chars=0,
        expects_exact_page_count=True,
        review_kind="slides",
    ),
    "xlsx": FormatAdapter(
        name="xlsx",
        suffix=".xlsx",
        mime_type=XLSX_MIME,
        convert_to_pdf=False,
        check=check_xlsx,
        requires_visual_review=False,
    ),
    "html": FormatAdapter(
        name="html",
        suffix=".html",
        mime_type=HTML_MIME,
        convert_to_pdf=False,
        check=check_html,
        requires_visual_review=False,
    ),
    "video": FormatAdapter(
        name="video",
        suffix=".mp4",
        mime_type=MP4_MIME,
        convert_to_pdf=False,
        check=reject_buffered_video_check,
        requires_visual_review=False,
        sandbox_check=check_video,
    ),
    "mindmap": FormatAdapter(
        name="mindmap",
        suffix=".png",
        mime_type=PNG_MIME,
        convert_to_pdf=False,
        check=check_mindmap_png,
        requires_visual_review=False,
        requires_markdown_binding=True,
        markdown_check=check_mindmap_markdown,
    ),
    "infographic": FormatAdapter(
        name="infographic",
        suffix=".png",
        mime_type=PNG_MIME,
        convert_to_pdf=False,
        check=check_infographic_png,
        requires_visual_review=False,
        requires_markdown_binding=True,
        markdown_check=check_infographic_markdown,
    ),
    "flashcards": FormatAdapter(
        name="flashcards",
        suffix=".json",
        mime_type="application/json",
        convert_to_pdf=False,
        check=check_flashcards_json,
        requires_visual_review=False,
        markdown_projection=flashcards_to_markdown,
    ),
    "quiz": FormatAdapter(
        name="quiz",
        suffix=".json",
        mime_type="application/json",
        convert_to_pdf=False,
        check=check_quiz_json,
        requires_visual_review=False,
        markdown_projection=quiz_to_markdown,
    ),
}


def get_format_adapter(format_name: str) -> FormatAdapter:
    """Return the verification policy for an explicit semantic format."""
    normalized = format_name.strip().lower()
    try:
        return _ADAPTERS[normalized]
    except KeyError:
        raise ValueError(
            f"Artifact verification does not support format {normalized or '(empty)'}"
        ) from None


def validate_format_path(adapter: FormatAdapter, path: str) -> None:
    """Reject a physical filename that does not match its declared format."""
    suffix = PurePosixPath(path).suffix.lower()
    if suffix != adapter.suffix:
        raise ValueError(
            f"{adapter.name} artifacts must use {adapter.suffix} files, got "
            f"{suffix or 'no extension'}"
        )
