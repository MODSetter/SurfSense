"""Measure PDF defects that do not require visual inspection."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from pypdf import PdfReader

from .base import StructuralCheckResult

DEFAULT_MARGIN_PT = 18 * 72 / 25.4
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


def _scan_text(
    page: Any, margin: float
) -> tuple[list[tuple[str, float, float]], list[str]]:
    """Return margin violations and unembedded fonts that actually draw text."""
    left = float(page.mediabox.left) + margin
    right = float(page.mediabox.right) - margin
    bottom = float(page.mediabox.bottom) + margin
    top = float(page.mediabox.top) - margin
    violations: list[tuple[str, float, float]] = []
    unembedded: dict[str, None] = {}

    def visitor(
        text: str,
        current_matrix: list[float],
        text_matrix: list[float],
        font: Any,
        _font_size: float,
    ) -> None:
        if not text.strip():
            return
        if font is not None and not _font_is_embedded(font):
            name = _object(font).get("/BaseFont", "unnamed font")
            unembedded.setdefault(str(name), None)
        x = (
            text_matrix[4] * current_matrix[0]
            + text_matrix[5] * current_matrix[2]
            + current_matrix[4]
        )
        y = (
            text_matrix[4] * current_matrix[1]
            + text_matrix[5] * current_matrix[3]
            + current_matrix[5]
        )
        if x < left or x > right or y < bottom or y > top:
            violations.append((text.strip()[:40], x, y))

    page.extract_text(visitor_text=visitor)
    return violations, list(unembedded)


def check_pdf(
    data: bytes,
    *,
    expected_pages: int | None = None,
    margin_pt: float = DEFAULT_MARGIN_PT,
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
            violations, unembedded = _scan_text(page, margin_pt)
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
        if violations:
            preview = ", ".join(
                f"{text!r} at ({x:.1f}, {y:.1f})" for text, x, y in violations[:5]
            )
            findings.append(f"page {number} has text outside the margins: {preview}")

    return StructuralCheckResult(page_count=page_count, findings=tuple(findings))
