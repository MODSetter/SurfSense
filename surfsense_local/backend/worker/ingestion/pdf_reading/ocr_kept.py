"""What OCR has read of a scan, kept when the reading gives the queue up, its own
or the Docling part's after it: the run that resumes reads only the pages left.

In ocr/ in the document's own folder (modules/documents/docling_batches/
layout.py): a folder, so original_file.py never takes it for the original, and
outside docling/, which a new Docling reading empties.
"""

import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from modules.documents.docling_batches.layout import ocr_dir

logger = logging.getLogger(__name__)

_FILE = "pages.json"
# 2: kept partway too, with the pages that read as text.
_FORMAT = 2


def kept_reading(original: Path, reader: str) -> dict[str, Any] | None:
    """The pages kept for these bytes by this reader, or None."""
    try:
        kept = json.loads((ocr_dir(original.parent) / _FILE).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    try:
        stamp = {"format": _FORMAT, "reader": reader, "original": _digest(original)}
    except OSError:
        return None
    if not isinstance(kept, dict) or kept.get("stamp") != stamp:
        return None
    return kept


def keep_reading(original: Path, reader: str, reading: dict[str, Any]) -> bool:
    """False when it could not be kept; never raises: without it a resume only
    reads the pages again."""
    folder = ocr_dir(original.parent)
    try:
        stamp = {"format": _FORMAT, "reader": reader, "original": _digest(original)}
        # Not parents: a source deleted meanwhile must not get its folder back.
        folder.mkdir(exist_ok=True)
        partial = folder / f"{_FILE}.partial"
        partial.write_text(json.dumps({"stamp": stamp, **reading}), "utf-8")
        partial.replace(folder / _FILE)
    except OSError as error:
        logger.warning("could not keep the OCR of %s: %s", original.name, error)
        return False
    return True


def forget_reading(original: Path) -> None:
    shutil.rmtree(ocr_dir(original.parent), ignore_errors=True)


def _digest(original: Path) -> str:
    digest = hashlib.sha256()
    with original.open("rb") as file:
        while block := file.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()
