"""How many slides, sheets or pages an Office file holds, read from its package without laying it out.

The API has no Office library to spare for a count, and a count needs only
the package's index parts.
"""

import re
import zipfile
from io import BytesIO
from pathlib import Path

_SLIDE = re.compile(rb"<(?:\w+:)?sldId\b")
# The deck's own slide list, which comes before any section's list of the same ids.
_SLIDE_LIST = re.compile(rb"<(\w+:|)sldIdLst\b[^>]*?(?:/>|>(.*?)</\1sldIdLst>)", re.S)
_SHEET = re.compile(rb"<(?:\w+:)?sheet\b")
_PAGES = re.compile(rb"<(?:\w+:)?Pages>\s*(\d+)\s*<")


def slide_count(file: bytes | Path) -> int | None:
    """The deck's slides, hidden ones included; None when it does not open."""
    found = _part(file, "ppt/presentation.xml")
    if found is None:
        return None
    listed = _SLIDE_LIST.search(found)
    return len(_SLIDE.findall(listed[2] or b"")) if listed else 0


def sheet_count(file: bytes | Path) -> int | None:
    """The workbook's sheets; None when it does not open."""
    found = _part(file, "xl/workbook.xml")
    return None if found is None else len(_SHEET.findall(found))


def word_saved_pages(file: bytes | Path) -> int | None:
    """The page count Word wrote when the file was last saved; most other writers write none."""
    found = _part(file, "docProps/app.xml")
    match = _PAGES.search(found) if found is not None else None
    return int(match[1]) if match else None


def _part(file: bytes | Path, name: str) -> bytes | None:
    try:
        with zipfile.ZipFile(
            BytesIO(file) if isinstance(file, bytes) else file
        ) as package:
            return package.read(name)
    except (zipfile.BadZipFile, KeyError, OSError):
        return None
