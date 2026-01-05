"""GitHub Connector Module."""

from .client import GitHubConnector
from .constants import MAX_FILE_SIZE, SKIPPED_DIRS
from .service import GitIngestService

__all__ = [
    "GitHubConnector",
    "GitIngestService",
    "MAX_FILE_SIZE",
    "SKIPPED_DIRS",
]

