"""
Constants for file document processing.

Centralizes file type classification, LlamaCloud retry configuration,
and timeout calculation parameters.
"""

import ssl
from enum import Enum

import httpx

# ---------------------------------------------------------------------------
# File type classification
# ---------------------------------------------------------------------------

MARKDOWN_EXTENSIONS = (".md", ".markdown", ".txt")
AUDIO_EXTENSIONS = (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")
DIRECT_CONVERT_EXTENSIONS = (".csv", ".tsv", ".html", ".htm")


class FileCategory(Enum):
    MARKDOWN = "markdown"
    AUDIO = "audio"
    DIRECT_CONVERT = "direct_convert"
    DOCUMENT = "document"


def classify_file(filename: str) -> FileCategory:
    """Classify a file by its extension into a processing category."""
    lower = filename.lower()
    if lower.endswith(MARKDOWN_EXTENSIONS):
        return FileCategory.MARKDOWN
    if lower.endswith(AUDIO_EXTENSIONS):
        return FileCategory.AUDIO
    if lower.endswith(DIRECT_CONVERT_EXTENSIONS):
        return FileCategory.DIRECT_CONVERT
    return FileCategory.DOCUMENT


# ---------------------------------------------------------------------------
# LlamaCloud retry configuration
# ---------------------------------------------------------------------------

LLAMACLOUD_MAX_RETRIES = 5
LLAMACLOUD_BASE_DELAY = 10  # seconds (exponential backoff base)
LLAMACLOUD_MAX_DELAY = 120  # max delay between retries (2 minutes)
LLAMACLOUD_RETRYABLE_EXCEPTIONS = (
    ssl.SSLError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.WriteError,
    httpx.WriteTimeout,
    httpx.RemoteProtocolError,
    httpx.LocalProtocolError,
    ConnectionError,
    ConnectionResetError,
    TimeoutError,
    OSError,
)

# ---------------------------------------------------------------------------
# Timeout calculation constants
# ---------------------------------------------------------------------------

UPLOAD_BYTES_PER_SECOND_SLOW = (
    100 * 1024
)  # 100 KB/s (conservative for slow connections)
MIN_UPLOAD_TIMEOUT = 120  # Minimum 2 minutes for any file
MAX_UPLOAD_TIMEOUT = 1800  # Maximum 30 minutes for very large files
BASE_JOB_TIMEOUT = 600  # 10 minutes base for job processing
PER_PAGE_JOB_TIMEOUT = 60  # 1 minute per page for processing
