"""Where a long Docling reading keeps the batches it has read: docling/work/ in
the document's folder. A folder, so original_file.py never takes it for the
original, and inside the document's own, so a delete removes it with the rest."""

from pathlib import Path

DOCLING_FOLDER = "docling"
WORK_FOLDER = "work"


def docling_dir(document_dir: Path) -> Path:
    return document_dir / DOCLING_FOLDER


def batches_dir(document_dir: Path) -> Path:
    return docling_dir(document_dir) / WORK_FOLDER
