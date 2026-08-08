#!/usr/bin/env python3
"""Measure PDF defects that do not require visual inspection."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pypdf import PdfReader

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


def _page_unembedded_fonts(page: Any) -> list[str]:
    resources = _object(page.get("/Resources", {}))
    fonts = _object(resources.get("/Font", {}))
    return [
        str(name)
        for name, font in fonts.items()
        if not _font_is_embedded(font)
    ]


def _text_margin_violations(page: Any, margin: float) -> list[tuple[str, float, float]]:
    left = float(page.mediabox.left) + margin
    right = float(page.mediabox.right) - margin
    bottom = float(page.mediabox.bottom) + margin
    top = float(page.mediabox.top) - margin
    violations: list[tuple[str, float, float]] = []

    def visitor(
        text: str,
        current_matrix: list[float],
        text_matrix: list[float],
        _font: Any,
        _font_size: float,
    ) -> None:
        if not text.strip():
            return
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
    return violations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--expect-pages", type=int)
    parser.add_argument("--margin-pt", type=float, default=DEFAULT_MARGIN_PT)
    parser.add_argument("--min-chars", type=int, default=DEFAULT_MIN_CHARS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path: Path = args.path
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"missing or empty PDF: {path}")
    reader = PdfReader(path)
    if not reader.pages:
        raise SystemExit("PDF has no pages")
    errors: list[str] = []
    if args.expect_pages is not None and len(reader.pages) != args.expect_pages:
        errors.append(
            f"expected {args.expect_pages} page(s), found {len(reader.pages)}"
        )

    for number, page in enumerate(reader.pages, start=1):
        text = "".join((page.extract_text() or "").split())
        if len(text) < args.min_chars:
            errors.append(
                f"page {number} is blank or near-blank "
                f"({len(text)} non-whitespace characters)"
            )
        unembedded = _page_unembedded_fonts(page)
        if unembedded:
            errors.append(
                f"page {number} has unembedded fonts: {', '.join(unembedded)}"
            )
        violations = _text_margin_violations(page, args.margin_pt)
        if violations:
            preview = ", ".join(
                f"{text!r} at ({x:.1f}, {y:.1f})"
                for text, x, y in violations[:5]
            )
            errors.append(f"page {number} has text outside the margins: {preview}")

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"ok: {len(reader.pages)} page(s), {path.stat().st_size} bytes")
    print(f"SURFSENSE_VERIFIED: {path}")


if __name__ == "__main__":
    main()
