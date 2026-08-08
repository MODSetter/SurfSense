#!/usr/bin/env python3
"""Fail fast on empty, unreadable, or blank-text PDFs."""

from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "")
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"missing or empty PDF: {path}")
    reader = PdfReader(path)
    if not reader.pages:
        raise SystemExit("PDF has no pages")
    blank = [
        number
        for number, page in enumerate(reader.pages, start=1)
        if not (page.extract_text() or "").strip()
    ]
    if blank:
        raise SystemExit(f"pages have no extractable text: {blank}")
    print(f"ok: {len(reader.pages)} page(s), {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
