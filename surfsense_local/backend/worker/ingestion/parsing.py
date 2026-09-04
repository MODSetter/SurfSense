import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from modules.documents.models import Document, DocumentType
from modules.documents.storage import original_path
from shared.config import get_storage_settings

# Already text: read off disk rather than round-trip through Docling.
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".text", ""}


def markdown_for(document: Document) -> str:
    """The document's text as markdown: note content, or a parsed file."""
    if document.document_type is not DocumentType.FILE:
        return document.content or ""

    path = original_path(document)
    if not path.is_file():
        raise FileNotFoundError("the uploaded file is no longer on disk")

    markdown = _markdown_from(path)
    # Kept beside the original so a reindex costs no re-parsing.
    (path.parent / "extracted.md").write_text(markdown, encoding="utf-8")
    return markdown


def _markdown_from(path: Path) -> str:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")

    return _converter().convert(path).document.export_to_markdown()


@lru_cache(maxsize=1)
def _converter() -> Any:
    """Built once per process: the constructor loads the layout models."""
    # Docling otherwise writes weights into site-packages, read-only in a
    # frozen bundle. Set before docling is imported.
    os.environ.setdefault("HF_HOME", str(get_storage_settings().models_dir))

    # Lazy: the import costs seconds and pulls in torch, which the API never needs.
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = True
    options.do_table_structure = True

    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
