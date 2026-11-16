"""What a long Docling reading has read, one file a conversion, named by what it
read: a yield or a restart carries on from here, and never reads the same pages
twice."""

import hashlib
import json
import logging
import shutil
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from worker.ingestion.parser_pack import missing_parser_folders

__all__ = ["ReadingCheckpoint"]

logger = logging.getLogger(__name__)

_STAMP = "stamp.json"
# Raised when a kept reading would mean something else to this code, as when the
# converter's options change and Docling's version does not.
_FORMAT = 1


class ReadingCheckpoint:
    """Opened for one original; readings of other bytes, by another Docling or
    with or without the parser pack, are dropped. `folder` lies inside the
    original's own folder, and `root`, the folder or one above it, is what goes
    when the reading ends."""

    def __init__(self, folder: Path, original: Path, root: Path | None = None) -> None:
        self._folder = folder
        self._root = root or folder
        self._home = original.parent
        self._stamp = {
            "format": _FORMAT,
            "original": _digest(original),
            "docling": _docling_version(),
            # As parsing._converter() reads it: only with the pack does OCR run
            # without RapidOCR's line classifier.
            "parser_pack": not missing_parser_folders(),
        }
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
            self._make_folder()
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

    def _make_folder(self) -> None:
        # Not parents: a source deleted meanwhile must not get its folder back.
        folder = self._home
        if not folder.is_dir():
            raise FileNotFoundError(f"{folder} is gone")
        for part in self._folder.relative_to(self._home).parts:
            folder = folder / part
            folder.mkdir(exist_ok=True)


def _digest(original: Path) -> str:
    """The original's bytes, so a file replaced with one of the same size is
    read again: 0.26 s for 100 MiB, once a run, where its pages take minutes."""
    digest = hashlib.sha256()
    with original.open("rb") as file:
        while block := file.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def _docling_version() -> str:
    try:
        return version("docling")
    except PackageNotFoundError:  # a bundle that dropped the metadata
        return "unknown"


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
