"""A born-digital PDF read from its own text layer, in milliseconds a page, where
Docling takes about 3 s a page; a page only Docling can read is named, page by page."""

from worker.ingestion.pdf_text_layer.reading import (
    LayerPage,
    TextLayer,
    read_text_layer,
)

__all__ = ["LayerPage", "TextLayer", "read_text_layer"]
