"""
Document processors module for background tasks.

This module provides a collection of document processors for different content types
and sources. Each processor is responsible for handling a specific type of document
processing task in the background.

Available processors:
- URL crawler: Process web pages from URLs
- Extension processor: Handle documents from browser extension
- Markdown processor: Process markdown files
- File processors: Handle files using different ETL services (Unstructured, LlamaCloud, Docling)
- YouTube processor: Process YouTube videos and extract transcripts
"""

# URL crawler
# Extension processor
from .extension_processor import add_extension_received_document

# File processors
from .file_processors import (
    add_received_file_document_using_docling,
    add_received_file_document_using_llamacloud,
    add_received_file_document_using_unstructured,
)

# Markdown processor
from .markdown_processor import add_received_markdown_file_document
from .url_crawler import add_crawled_url_document

# YouTube processor
from .youtube_processor import add_youtube_video_document

__all__ = [
    # URL processing
    "add_crawled_url_document",
    # Extension processing
    "add_extension_received_document",
    "add_received_file_document_using_docling",
    "add_received_file_document_using_llamacloud",
    # File processing with different ETL services
    "add_received_file_document_using_unstructured",
    # Markdown file processing
    "add_received_markdown_file_document",
    # YouTube video processing
    "add_youtube_video_document",
]
