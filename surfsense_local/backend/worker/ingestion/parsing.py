import logging
import os
from contextlib import nullcontext
from functools import lru_cache
from pathlib import Path
from typing import Any

import psutil

from modules.documents.models import Document, DocumentType
from modules.documents.original_file import original_path
from modules.documents.recordings.kind import is_recording
from modules.documents.source_figures.figures_pass import queue_figures_pass
from modules.documents.source_figures.layout import figures_dir, read_index
from modules.documents.tasks import PRIORITY_IDLE
from modules.documents.text_files import TEXT_SUFFIXES
from shared.config import get_storage_settings
from worker.ingestion.audio.transcript_job import recording_markdown
from worker.ingestion.docx_style_cache import cached_style_lookups
from worker.ingestion.figures.store import keep_figures
from worker.ingestion.figures.word_figures_pass import leave_figures_to_the_pass
from worker.ingestion.image_page import IMAGE_SUFFIXES, as_page
from worker.ingestion.parser_pack import missing_parser_folders, parser_dir
from worker.ingestion.pdf_text_layer import read_text_layer
from worker.ingestion.slideless_deck import describe_slideless_deck
from worker.ingestion.word_markdown import markdown_without_docling

logger = logging.getLogger(__name__)


class UnreadableFileError(Exception):
    """Docling could not load the file's bytes, so it would refuse them again."""


def markdown_for(document: Document) -> str:
    """The document's text as markdown: note content, or a parsed file."""
    if document.document_type is not DocumentType.FILE:
        return document.content or ""

    path = original_path(document)
    if path is None:
        raise FileNotFoundError("the uploaded file is no longer on disk")

    # Before Docling, which must never read a recording.
    if is_recording(document.mime_type):
        return recording_markdown(document, path)
    if path.suffix.lower() == ".pdf":
        text = _text_layer(document, path)
        if text is not None:
            return text
    return _markdown_from(path)


def _text_layer(document: Document, path: Path) -> str | None:
    """A born-digital PDF's own text, or None when Docling must read the file."""
    layer = read_text_layer(path)
    if layer.text is None:
        logger.info("Docling reads %s: %s", path.name, layer.refused_because)
        return None
    if layer.images and read_index(figures_dir(path.parent)) is None:
        # Ready without its figures; Docling keeps them once nothing else waits.
        queue_figures_pass(document.id, PRIORITY_IDLE)
    return layer.text


def _markdown_from(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx" and (markdown := markdown_without_docling(path)) is not None:
        # Its figures come from the figures-only pass, which still asks Docling.
        leave_figures_to_the_pass(path)
        return markdown

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
    from docling.exceptions import ConversionError, DocumentLoadError

    suffix = path.suffix.lower()
    source = as_page(path) if suffix in IMAGE_SUFFIXES else path
    reading = cached_style_lookups() if suffix == ".docx" else nullcontext()
    try:
        with reading:
            return converter.convert(source).document
    except ConversionError as refused:
        # Docling also reports a file it cannot open yet and a model that ran
        # out of memory this way; only bytes it cannot load fail the same again.
        if isinstance(refused.__cause__, DocumentLoadError):
            raise UnreadableFileError(str(refused)) from refused
        raise


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
