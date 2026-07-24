"""
Document processors module for background tasks.

Content extraction is handled by ``app.etl_pipeline.EtlPipelineService``.
This package keeps orchestration (save, notify, page-limit) and
non-ETL processors (extension, markdown).
"""

from .extension_processor import add_extension_received_document
from .markdown_processor import add_received_markdown_file_document

__all__ = [
    "add_extension_received_document",
    "add_received_markdown_file_document",
]
