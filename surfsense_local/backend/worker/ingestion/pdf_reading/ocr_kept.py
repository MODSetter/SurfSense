"""What OCR read of a scan whose garbled pages Docling still reads: a Docling
reading that gives the queue up resumes from here instead of reading every page
with OCR again.

In ocr/ in the document's own folder: a folder, so original_file.py never takes it
for the original, and outside docling/, which a new Docling reading empties.
"""

import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FOLDER = "ocr"
_FILE = "pages.json"
_FORMAT = 1


def kept_reading(original: Path, reader: str) -> dict[str, Any] | None:
    """The pages kept for these bytes by this reader, or None."""
    try:
        kept = json.loads((original.parent / FOLDER / _FILE).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    try:
        stamp = {"format": _FORMAT, "reader": reader, "original": _digest(original)}
    except OSError:
        return None
    if not isinstance(kept, dict) or kept.get("stamp") != stamp:
        return None
    return kept


def keep_reading(original: Path, reader: str, reading: dict[str, Any]) -> None:
    """Never raises: without it a resume only reads the pages again."""
    folder = original.parent / FOLDER
    try:
        stamp = {"format": _FORMAT, "reader": reader, "original": _digest(original)}
        # Not parents: a source deleted meanwhile must not get its folder back.
        folder.mkdir(exist_ok=True)
        partial = folder / f"{_FILE}.partial"
        partial.write_text(json.dumps({"stamp": stamp, **reading}), "utf-8")
        partial.replace(folder / _FILE)
    except OSError as error:
        logger.warning("could not keep the OCR of %s: %s", original.name, error)


def forget_reading(original: Path) -> None:
    shutil.rmtree(original.parent / FOLDER, ignore_errors=True)


def _digest(original: Path) -> str:
    digest = hashlib.sha256()
    with original.open("rb") as file:
        while block := file.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()
