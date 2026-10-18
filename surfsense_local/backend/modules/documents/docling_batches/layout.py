"""Where a long reading keeps what it has read when it gives the queue up:
Docling's batches in docling/work/ in the document's folder, OCR's pages in ocr/.
Folders, so original_file.py never takes one for the original, and inside the
document's own, so a delete removes them with the rest."""

from pathlib import Path

DOCLING_FOLDER = "docling"
WORK_FOLDER = "work"
OCR_FOLDER = "ocr"


def docling_dir(document_dir: Path) -> Path:
    return document_dir / DOCLING_FOLDER


def batches_dir(document_dir: Path) -> Path:
    return docling_dir(document_dir) / WORK_FOLDER


def ocr_dir(document_dir: Path) -> Path:
    return document_dir / OCR_FOLDER
