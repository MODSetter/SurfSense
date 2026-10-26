"""The seam parsing calls: a .docx read here, or None to leave it to Docling."""

import logging
import zipfile
from pathlib import Path

from worker.ingestion.word_markdown.document import markdown_of
from worker.ingestion.word_markdown.reader_switch import reads_docx_here

log = logging.getLogger(__name__)


def markdown_without_docling(path: Path) -> str | None:
    """None when the switch says Docling, when the file holds native charts,
    when this reader fails, or when it finds no text: Docling then reads the
    file as before, and what it says of a blank file stays today's answer."""
    if not reads_docx_here():
        return None
    try:
        if _has_charts(path):
            return None
        markdown = markdown_of(path)
    except Exception:
        log.warning(
            "Docling reads %s: the Word reader failed", path.name, exc_info=True
        )
        return None
    return markdown if markdown.strip() else None


def _has_charts(path: Path) -> bool:
    # Docling turns a chart's cached data into a table this reader does not write.
    with zipfile.ZipFile(path) as package:
        return any(name.startswith("word/charts/") for name in package.namelist())
