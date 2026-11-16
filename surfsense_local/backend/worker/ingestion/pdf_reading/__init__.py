"""A PDF as markdown: from its own text layer, from Docling for the pages only it
can read with the text layer for the rest, or from Docling whole."""

from worker.ingestion.pdf_reading.route import pdf_markdown

__all__ = ["pdf_markdown"]
