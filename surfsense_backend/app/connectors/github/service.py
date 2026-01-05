"""
Gitingest service for processing GitHub repositories.

This module provides a wrapper around the gitingest library to convert
GitHub repositories into text format optimized for indexing and LLM processing.
"""

import asyncio
import logging
from typing import Any

from .constants import MAX_FILE_SIZE, SKIPPED_DIRS

logger = logging.getLogger(__name__)


class GitIngestService:
    """Service for processing GitHub repositories using gitingest."""

    def __init__(self, token: str | None = None):
        self.token = token
        self.max_file_size = MAX_FILE_SIZE
        logger.info("GitIngest service initialized")

    async def process_repository(
        self, repo_url: str, branch: str = "main"
    ) -> dict[str, Any]:
        """
        Process a GitHub repository and extract its content asynchronously.

        Uses gitingest's native ingest_async function for proper async support
        within Celery tasks and other async contexts.

        Args:
            repo_url: GitHub repository URL (e.g., "https://github.com/owner/repo")
            branch: Branch to process (default: "main")

        Returns:
            Dictionary containing content, tree, summary, and metadata
        """
        try:
            try:
                from gitingest import ingest_async
            except ImportError:
                logger.error("gitingest package not installed")
                raise ImportError(
                    "gitingest is required. Install with: pip install gitingest"
                )

            logger.info(f"Processing repository: {repo_url} (branch: {branch})")
            repo_full_name = self._parse_repo_url(repo_url)

            exclude_patterns = [f"{dir_name}/**" for dir_name in SKIPPED_DIRS]
            exclude_patterns.append("*.pyc")

            # Use gitingest's native async function for non-blocking operation
            # ingest_async returns a tuple: (summary, tree, content)
            summary, tree, content = await ingest_async(
                query=repo_url,
                max_file_size=self.max_file_size,
                include_patterns=None,
                exclude_patterns=exclude_patterns,
            )

            logger.info(
                f"Successfully processed repository {repo_full_name}: {len(content)} characters"
            )

            return {
                "content": content,
                "tree": tree,
                "summary": summary,
                "repo_full_name": repo_full_name,
                "branch": branch,
                "metadata": {
                    "repository": repo_full_name,
                    "branch": branch,
                    "source": "gitingest",
                    "content_length": len(content),
                },
            }

        except ImportError:
            raise
        except Exception as e:
            logger.error(f"Failed to process repository {repo_url}: {e}", exc_info=True)
            raise ValueError(f"Failed to process repository: {e!s}") from e

    def _parse_repo_url(self, repo_url: str) -> str:
        """Parse GitHub repository URL to extract owner/repo format."""
        if not repo_url:
            raise ValueError("Repository URL cannot be empty")

        repo_url = repo_url.rstrip("/")

        if repo_url.endswith(".git"):
            repo_url = repo_url[:-4]

        if "github.com/" in repo_url:
            parts = repo_url.split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
            else:
                raise ValueError(f"Invalid GitHub URL format: {repo_url}")
        elif "/" in repo_url and repo_url.count("/") == 1:
            return repo_url
        else:
            raise ValueError(
                f"Invalid repository URL format: {repo_url}. "
                f"Expected format: 'owner/repo' or 'https://github.com/owner/repo'"
            )

    async def process_multiple_repositories(
        self, repo_urls: list[str], branch: str = "main"
    ) -> dict[str, dict[str, Any]]:
        """
        Process multiple GitHub repositories asynchronously and return results with errors.
        
        Processes repositories sequentially to avoid overwhelming the system.
        """
        results = {}
        errors = {}

        for repo_url in repo_urls:
            try:
                result = await self.process_repository(repo_url, branch)
                repo_name = result["repo_full_name"]
                results[repo_name] = result
                logger.info(f"✓ Successfully processed {repo_name}")
            except Exception as e:
                repo_name = repo_url
                errors[repo_name] = str(e)
                logger.error(f"✗ Failed to process {repo_name}: {e}")

        if errors:
            logger.warning(
                f"Processed {len(results)}/{len(repo_urls)} repositories successfully. "
                f"{len(errors)} failed."
            )

        return {
            "results": results,
            "errors": errors,
            "success_count": len(results),
            "error_count": len(errors),
        }

