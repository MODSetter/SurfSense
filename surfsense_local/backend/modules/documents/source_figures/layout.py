"""Where a source's figures live: figures/<n>.png and figures.json beside its original.

Inside the document's own folder, so deleting the source deletes them and no
table or migration is needed.
"""

import json
from pathlib import Path
from typing import Any

from modules.documents.storage import UPLOAD_MIME_BY_SUFFIX

FIGURES_FOLDER = "figures"
INDEX_NAME = "figures.json"
INDEX_VERSION = 1


def figures_dir(document_dir: Path) -> Path:
    return document_dir / FIGURES_FOLDER


def figure_png(folder: Path, n: int) -> Path:
    return folder / f"{n}.png"


def can_hold_figures(original: Path) -> bool:
    """Text uploads carry no pictures; Docling drops an HTML page's linked ones."""
    mime = UPLOAD_MIME_BY_SUFFIX.get(original.suffix.lower(), "")
    return not mime.startswith("text/")


def read_index(folder: Path) -> list[dict[str, Any]] | None:
    """The kept figures' entries, or None when no complete index is there."""
    try:
        index = json.loads((folder / INDEX_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(index, dict) or index.get("version") != INDEX_VERSION:
        return None
    entries = index.get("figures")
    if not isinstance(entries, list) or not all(map(_is_entry, entries)):
        return None
    return entries


def write_index(folder: Path, entries: list[dict[str, Any]], error: str | None) -> None:
    """Written last and replaced whole, so a reader never sees half an index."""
    index: dict[str, Any] = {"version": INDEX_VERSION, "figures": entries}
    if error is not None:
        index["error"] = error
    partial = folder / f"{INDEX_NAME}.partial"
    partial.write_text(json.dumps(index), encoding="utf-8")
    partial.replace(folder / INDEX_NAME)


def _is_entry(entry: object) -> bool:
    return (
        isinstance(entry, dict)
        and _is_int(entry.get("n"))
        and _is_int(entry.get("width"))
        and _is_int(entry.get("height"))
        and (entry.get("page") is None or _is_int(entry.get("page")))
        and (entry.get("caption") is None or isinstance(entry.get("caption"), str))
    )


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
