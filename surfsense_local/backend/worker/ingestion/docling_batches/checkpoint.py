"""What a long Docling reading has read, one file a conversion, named by what it
read: a yield, a retry or a restart carries on from here, and never reads the
same pages twice."""

import json
import logging
import shutil
from importlib.metadata import version
from pathlib import Path
from typing import Any

__all__ = ["ReadingCheckpoint"]

logger = logging.getLogger(__name__)

_STAMP = "stamp.json"


class ReadingCheckpoint:
    """Opened for one original; readings of another file, or by another Docling,
    are dropped. `root` is what goes when the reading ends: the folder or above."""

    def __init__(self, folder: Path, original: Path, root: Path | None = None) -> None:
        self._folder = folder
        self._root = root or folder
        self._stamp = {"size": original.stat().st_size, "docling": version("docling")}
        if _json_of(folder / _STAMP) != self._stamp:
            self.drop()

    def done(self, name: str) -> tuple[Any, Any] | None:
        """The DoclingDocument kept under `name` and its notes, or None when no
        whole one was kept."""
        from docling_core.types.doc import DoclingDocument

        kept = _json_of(self._folder / f"{name}.json")
        try:
            return DoclingDocument.model_validate(kept["document"]), kept.get("notes")
        except (TypeError, KeyError, ValueError):
            return None

    def keep(self, name: str, document: Any, notes: Any = None) -> bool:
        """False when the disk refused it: those pages would be read again."""
        entry = {"notes": notes, "document": document.model_dump(mode="json")}
        try:
            self._folder.mkdir(parents=True, exist_ok=True)
            stamp = self._folder / _STAMP
            if not stamp.is_file():
                _write(stamp, json.dumps(self._stamp))
            _write(self._folder / f"{name}.json", json.dumps(entry))
        except OSError as error:
            logger.warning("could not keep %s of %s: %s", name, self._folder, error)
            return False
        return True

    def drop(self) -> None:
        shutil.rmtree(self._root, ignore_errors=True)


def _json_of(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # none there, or a file the last run was writing when it stopped


def _write(path: Path, text: str) -> None:
    """Replaced whole, so a run that stops midway leaves no half a reading."""
    partial = path.with_name(f"{path.name}.partial")
    partial.write_text(text, encoding="utf-8")
    partial.replace(path)
