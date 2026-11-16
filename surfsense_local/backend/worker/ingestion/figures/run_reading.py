"""Docling's reading of a run of a PDF's pages: in full, or by its layout model alone."""

import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple

from worker.ingestion import parsing


class LayoutReading(NamedTuple):
    document: Any  # a DoclingDocument
    captions_for_ocr: frozenset[int]  # pages with a caption only OCR could read


def read_in_full(pdf: Path, first: int, last: int) -> Any:
    """Pages first to last as ingest reads them, OCR and TableFormer included."""
    return parsing._converter().convert(pdf, page_range=(first, last)).document


def read_by_layout(pdf: Path, first: int, last: int) -> LayoutReading:
    """Pages first to last read by the layout model, without OCR or TableFormer."""
    converter, captions = _layout_converter()
    from docling.datamodel.base_models import ConversionStatus

    # One reading at a time: the noted pages are the converter's.
    with _one_reading:
        captions.pages.clear()
        result = converter.convert(pdf, page_range=(first, last))
        noted = frozenset(captions.pages)
    # Docling keeps a page it failed on, empty; the full reading decides there.
    if result.status is not ConversionStatus.SUCCESS:
        raise RuntimeError(f"layout alone read pages {first}-{last} {result.status}")
    return LayoutReading(result.document, noted)


_one_reading = threading.Lock()


@lru_cache(maxsize=1)
def _layout_converter() -> tuple[Any, Any]:
    """Built once per process; the first reading then loads the layout model."""
    # First: ingest's own options (its parser pack, layout model and threads),
    # and the environment it sets before docling is first imported.
    full = parsing._converter()
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption

    from worker.ingestion.figures.captions_for_ocr import (
        CaptionsForOcr,
        layout_only_pipeline,
    )

    options = full.format_to_options[InputFormat.PDF].pipeline_options.model_copy(
        update={"do_ocr": False, "do_table_structure": False}
    )
    captions = CaptionsForOcr()
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=layout_only_pipeline(captions), pipeline_options=options
            )
        },
    )
    return converter, captions
