"""GitHub Connector Module using Gitingest."""

from .constants import MAX_FILE_SIZE, SKIPPED_DIRS
from .gitingest_client import GitHubConnectorGitingest
from .gitingest_service import GitIngestService

GitHubConnector = GitHubConnectorGitingest

__all__ = [
    "GitHubConnector",
    "GitHubConnectorGitingest",
    "GitIngestService",
    "MAX_FILE_SIZE",
    "SKIPPED_DIRS",
]

