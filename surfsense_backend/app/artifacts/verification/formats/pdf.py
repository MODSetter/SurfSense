"""Measure PDF defects that do not require visual inspection."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from pypdf import PdfReader

from .base import StructuralCheckResult

DEFAULT_MIN_CHARS = 20


def _object(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def _font_is_embedded(font: Any) -> bool:
    font = _object(font)
    descendants = _object(font.get("/DescendantFonts", []))
    candidates = [_object(item) for item in descendants] or [font]
    for candidate in candidates:
        descriptor = _object(candidate.get("/FontDescriptor"))
        if descriptor and any(
            descriptor.get(key) is not None
            for key in ("/FontFile", "/FontFile2", "/FontFile3")
        ):
            return True
    return False


def _unembedded_fonts(page: Any) -> list[str]:
    """Return unembedded fonts that actually draw text."""
    unembedded: dict[str, None] = {}

    def visitor(
        text: str,
        _current_matrix: list[float],
        _text_matrix: list[float],
        font: Any,
        _font_size: float,
    ) -> None:
        if not text.strip():
            return
        if font is not None and not _font_is_embedded(font):
            name = _object(font).get("/BaseFont", "unnamed font")
            unembedded.setdefault(str(name), None)

    page.extract_text(visitor_text=visitor)
    return list(unembedded)


def check_pdf(
    data: bytes,
    *,
    expected_pages: int | None = None,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> StructuralCheckResult:
    """Check PDF bytes and return all structural findings."""
    if not data:
        return StructuralCheckResult(page_count=0, findings=("PDF is empty",))

    try:
        reader = PdfReader(BytesIO(data))
        page_count = len(reader.pages)
    except Exception as exc:
        return StructuralCheckResult(
            page_count=0,
            findings=(f"PDF could not be parsed: {exc}",),
        )
    if page_count == 0:
        return StructuralCheckResult(page_count=0, findings=("PDF has no pages",))

    findings: list[str] = []
    if expected_pages is not None and page_count != expected_pages:
        findings.append(f"expected {expected_pages} page(s), found {page_count}")

    for number, page in enumerate(reader.pages, start=1):
        try:
            text = "".join((page.extract_text() or "").split())
            unembedded = _unembedded_fonts(page)
        except Exception as exc:
            findings.append(f"page {number} could not be inspected: {exc}")
            continue
        if len(text) < min_chars:
            findings.append(
                f"page {number} is blank or near-blank "
                f"({len(text)} non-whitespace characters)"
            )
        if unembedded:
            findings.append(
                f"page {number} draws text in unembedded fonts: {', '.join(unembedded)}"
            )

    return StructuralCheckResult(page_count=page_count, findings=tuple(findings))
