"""A born-digital PDF read from its own text layer, in milliseconds a page, where
Docling takes about 3 s a page; any page only Docling can read sends it the file."""

from worker.ingestion.pdf_text_layer.reading import TextLayer, read_text_layer

__all__ = ["TextLayer", "read_text_layer"]
