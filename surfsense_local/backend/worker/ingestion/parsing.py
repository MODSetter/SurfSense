import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import psutil

from modules.documents.models import Document, DocumentType
from modules.documents.original_file import original_path
from shared.config import get_storage_settings
from worker.ingestion.figures.store import keep_figures
from worker.ingestion.image_page import IMAGE_SUFFIXES, as_page
from worker.ingestion.parser_pack import missing_parser_folders, parser_dir
from worker.ingestion.slideless_deck import describe_slideless_deck

# Already text: read off disk rather than round-trip through Docling.
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".text"}


class UnreadableFileError(Exception):
    """Docling refused the file itself, so it would refuse the same bytes again."""


def markdown_for(document: Document) -> str:
    """The document's text as markdown: note content, or a parsed file."""
    if document.document_type is not DocumentType.FILE:
        return document.content or ""

    path = original_path(document)
    if path is None:
        raise FileNotFoundError("the uploaded file is no longer on disk")

    return _markdown_from(path)


def _markdown_from(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")

    converted = convert(path)
    keep_figures(path, converted)
    template = describe_slideless_deck(path)
    return converted.export_to_markdown() if template is None else template


def convert(path: Path) -> Any:
    """Docling's reading of a file: its DoclingDocument."""
    if describe_slideless_deck(path) is not None:
        from docling_core.types.doc import DoclingDocument

        # Nothing for Docling to read, and it refuses a deck with no pages.
        return DoclingDocument(name=path.stem)

    # First: it sets the environment docling reads as it is imported.
    converter = _converter()
    from docling.exceptions import ConversionError

    source = as_page(path) if path.suffix.lower() in IMAGE_SUFFIXES else path
    try:
        return converter.convert(source).document
    except ConversionError as refused:
        raise UnreadableFileError(str(refused)) from refused


@lru_cache(maxsize=1)
def _converter() -> Any:
    """Built once per process; the first conversion then loads the models."""
    # Docling otherwise writes weights into site-packages, read-only in a
    # frozen bundle. Set before docling is imported.
    os.environ.setdefault("HF_HOME", str(get_storage_settings().models_dir))
    pack_ready = not missing_parser_folders()
    if pack_ready:
        # huggingface_hub reads this once, when docling first imports it.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

    # Lazy: the import costs seconds and pulls in torch, which the API never needs.
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
    from docling.document_converter import (
        DocumentConverter,
        ImageFormatOption,
        PdfFormatOption,
    )

    options = PdfPipelineOptions()
    options.do_ocr = True
    options.do_table_structure = True
    # No picture images: figures are cropped from the original afterwards
    # (figures/pdf_crops.py), as these keep every page's render in memory.
    # Docling's default is 4 threads; one per physical core parsed 1.4x faster
    # on 8 cores. At most 8, as for audio.cpp, since chat may share the CPU.
    options.accelerator_options = AcceleratorOptions(
        num_threads=min(8, psutil.cpu_count(logical=False) or 4)
    )
    if pack_ready:
        options.artifacts_path = parser_dir()
        # The line classifier turns upright lines of a noisy scan 180 degrees,
        # which then read as garbage; it cut scan error rates 8x to drop it.
        options.ocr_options = RapidOcrOptions(use_cls=False)

    return DocumentConverter(
        allowed_formats=[
            InputFormat.PDF,
            InputFormat.DOCX,
            InputFormat.PPTX,
            InputFormat.XLSX,
            InputFormat.HTML,
            InputFormat.CSV,
            InputFormat.MD,
            InputFormat.IMAGE,
        ],
        # The same options object: images read the pack too, and share the
        # PDF pipeline instead of loading a second copy of every model.
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=options),
        },
    )
