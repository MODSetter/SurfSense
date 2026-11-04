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
        # The app's own Word reader, the one ingest uses unless switched to Docling.
        from worker.ingestion.word_markdown.document import markdown_of

        text = markdown_of(path)
    elif suffix == ".pdf":
        text = _pdf_text(path)
    else:
        raise ValueError(
            f"{path.name}: the eval reads .md, .txt, .docx and .pdf sources"
        )
    return SourceText(document_id, path.stem, text)


def _pdf_text(path: Path) -> str:
    """A born-digital PDF's text layer, page by page, as ingest reads it first (ADR 0059)."""
    import pypdfium2

    pdf = pypdfium2.PdfDocument(str(path))
    try:
        pages = []
        for page in pdf:
            text = page.get_textpage().get_text_range()
            pages.append(text.replace("\r\n", "\n").strip())
        return "\n\n".join(pages)
    finally:
        pdf.close()
