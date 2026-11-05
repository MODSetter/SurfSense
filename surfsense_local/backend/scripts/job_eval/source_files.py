"""A case's policy files as the text the app's ingest makes of them, so the eval reads what the job reads."""

from __future__ import annotations

from pathlib import Path

from modules.jobs.evidence.passages import SourceText

TEXT_SUFFIXES = (".md", ".txt")


def source_text(path: Path, document_id: int) -> SourceText:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        text = path.read_text(encoding="utf-8")
    elif suffix == ".docx":
        text = _word_text(path)
    elif suffix == ".pdf":
        text = _pdf_text(path)
    else:
        raise ValueError(
            f"{path.name}: the eval reads .md, .txt, .docx and .pdf sources"
        )
    return SourceText(document_id, path.stem, text)


def _word_text(path: Path) -> str:
    """The app's own Word reader, as ingest chooses it; a file ingest gives Docling is refused."""
    from worker.ingestion.word_markdown import markdown_without_docling

    text = markdown_without_docling(path)
    if text is None:
        raise ValueError(
            f"{path.name}: ingest reads this Word file with Docling (charts, no text, "
            "a reader failure or SURFSENSE_LOCAL_DOCX_READER), which the eval does not run"
        )
    return text


def _pdf_text(path: Path) -> str:
    """The text layer ingest stores for a born-digital PDF (ADR 0059); a PDF ingest gives
    OCR or Docling is refused, since its pages would read differently or not at all."""
    from worker.ingestion.pdf_text_layer import read_text_layer

    layer = read_text_layer(path)
    if layer.text is None:
        raise ValueError(
            f"{path.name}: ingest reads this PDF with OCR or Docling "
            f"({layer.refused_because}), which the eval does not run"
        )
    return layer.text
