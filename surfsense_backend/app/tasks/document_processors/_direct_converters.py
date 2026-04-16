"""
Lossless file-to-markdown converters for text-based formats.

These converters handle file types that can be faithfully represented as
markdown without any external ETL/OCR service:

- CSV / TSV          → markdown table  (stdlib ``csv``)
- HTML / HTM / XHTML → markdown        (``markdownify``)
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

from markdownify import markdownify

# The stdlib csv module defaults to a 128 KB field-size limit which is too
# small for real-world exports (e.g. chat logs, CRM dumps).  We raise it once
# at import time so every csv.reader call in this module can handle large fields.
csv.field_size_limit(2**31 - 1)

_BOM_ENCODINGS: list[tuple[bytes, str]] = [
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
]


def _detect_encoding(file_path: str) -> str:
    """Sniff the BOM to pick an encoding, falling back to utf-8."""
    head = Path(file_path).read_bytes()[:4]
    for bom, encoding in _BOM_ENCODINGS:
        if head.startswith(bom):
            return encoding
    return "utf-8"


def _read_text(file_path: str) -> str:
    """Read a file with automatic encoding detection.

    Tries BOM-based detection first, then utf-8, then latin-1 as a
    last resort (latin-1 accepts every byte value).
    """
    encoding = _detect_encoding(file_path)
    try:
        return Path(file_path).read_text(encoding=encoding)
    except (UnicodeDecodeError, UnicodeError):
        pass
    if encoding != "utf-8":
        try:
            return Path(file_path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, UnicodeError):
            pass
    return Path(file_path).read_text(encoding="latin-1")


def _escape_pipe(cell: str) -> str:
    """Escape literal pipe characters inside a markdown table cell."""
    return cell.replace("|", "\\|")


def csv_to_markdown(file_path: str, *, delimiter: str = ",") -> str:
    """Convert a CSV (or TSV) file to a markdown table.

    The first row is treated as the header.  An empty file returns an
    empty string so the caller can decide how to handle it.
    """
    text = _read_text(file_path)
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    rows = list(reader)

    if not rows:
        return ""

    header, *body = rows
    col_count = len(header)

    lines: list[str] = []

    header_cells = [_escape_pipe(c.strip()) for c in header]
    lines.append("| " + " | ".join(header_cells) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")

    for row in body:
        padded = row + [""] * (col_count - len(row))
        cells = [_escape_pipe(c.strip()) for c in padded[:col_count]]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines) + "\n"


def tsv_to_markdown(file_path: str) -> str:
    """Convert a TSV file to a markdown table."""
    return csv_to_markdown(file_path, delimiter="\t")


def html_to_markdown(file_path: str) -> str:
    """Convert an HTML file to markdown via ``markdownify``."""
    html = _read_text(file_path)
    return markdownify(html).strip()


_CONVERTER_MAP: dict[str, Callable[..., str]] = {
    ".csv": csv_to_markdown,
    ".tsv": tsv_to_markdown,
    ".html": html_to_markdown,
    ".htm": html_to_markdown,
    ".xhtml": html_to_markdown,
}


def convert_file_directly(file_path: str, filename: str) -> str:
    """Dispatch to the appropriate lossless converter based on file extension.

    Raises ``ValueError`` if the extension is not supported.
    """
    suffix = Path(filename).suffix.lower()
    converter = _CONVERTER_MAP.get(suffix)
    if converter is None:
        raise ValueError(
            f"No direct converter for extension '{suffix}' (file: {filename})"
        )
    return converter(file_path)
