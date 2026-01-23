"""
GitHub connector using gitingest CLI for efficient repository digestion.

This connector uses subprocess to call gitingest CLI, completely isolating
it from any Python event loop/async complexity that can cause hangs in Celery.
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Maximum file size in bytes (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024


@dataclass
class RepositoryDigest:
    """Represents a digested repository from gitingest."""

    repo_full_name: str
    summary: str
    tree: str
    content: str
    branch: str | None = None

    @property
    def full_digest(self) -> str:
        """Returns the complete digest with tree and content."""
        return f"# Repository: {self.repo_full_name}\n\n## File Structure\n\n{self.tree}\n\n## File Contents\n\n{self.content}"

    @property
    def estimated_tokens(self) -> int:
        """Rough estimate of tokens (1 token ≈ 4 characters)."""
        return len(self.full_digest) // 4


class GitHubConnector:
    """
    Connector for ingesting GitHub repositories using gitingest CLI.

    Uses subprocess to run gitingest, which avoids all async/event loop
    issues that can occur when mixing gitingest with Celery workers.
    """

    def __init__(self, token: str | None = None):
        """
        Initialize the GitHub connector.

        Args:
            token: Optional GitHub Personal Access Token (PAT).
                   Only required for private repositories.
        """
        self.token = token if token and token.strip() else None
        if self.token:
            logger.info("GitHub connector initialized with authentication token.")
        else:
            logger.info(
                "GitHub connector initialized without token (public repos only)."
            )

    def ingest_repository(
        self,
        repo_full_name: str,
        branch: str | None = None,
        max_file_size: int = MAX_FILE_SIZE,
    ) -> RepositoryDigest | None:
        """
        Ingest a repository using gitingest CLI via subprocess.

        This approach completely isolates gitingest from Python's event loop,
        avoiding any async/Celery conflicts.

        Args:
            repo_full_name: The full name of the repository (e.g., 'owner/repo').
            branch: Optional specific branch or tag to ingest.
            max_file_size: Maximum file size in bytes to include.

        Returns:
            RepositoryDigest or None if ingestion fails.
        """
        repo_url = f"https://github.com/{repo_full_name}"

        logger.info(f"Starting gitingest CLI for repository: {repo_full_name}")

        try:
            # Create a temporary file for output
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            ) as tmp_file:
                output_path = tmp_file.name

            # Build the gitingest CLI command
            cmd = [
                "gitingest",
                repo_url,
                "--output",
                output_path,
                "--max-size",
                str(max_file_size),
                # Common exclude patterns
                "-e",
                "node_modules/*",
                "-e",
                "vendor/*",
                "-e",
                ".git/*",
                "-e",
                "__pycache__/*",
                "-e",
                "dist/*",
                "-e",
                "build/*",
                "-e",
                "*.lock",
                "-e",
                "package-lock.json",
            ]

            # Add branch if specified
            if branch:
                cmd.extend(["--branch", branch])

            # Set up environment with token if provided
            env = os.environ.copy()
            if self.token:
                env["GITHUB_TOKEN"] = self.token

            logger.info(f"Running gitingest CLI: {' '.join(cmd[:5])}...")

            # Run gitingest as subprocess with timeout
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=900,  # 5 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"gitingest failed: {result.stderr}")
                # Clean up temp file
                if os.path.exists(output_path):
                    os.unlink(output_path)
                return None

            # Read the output file
            if not os.path.exists(output_path):
                logger.error("gitingest did not create output file")
                return None

            with open(output_path, encoding="utf-8") as f:
                full_content = f.read()

            # Clean up temp file
            os.unlink(output_path)

            if not full_content or not full_content.strip():
                logger.warning(
                    f"No content retrieved from repository: {repo_full_name}"
                )
                return None

            # Parse the gitingest output
            # The output format is: summary + tree + content
            # We'll extract what we can
            digest = RepositoryDigest(
                repo_full_name=repo_full_name,
                summary=f"Repository: {repo_full_name}",
                tree="",  # gitingest CLI combines everything into one file
                content=full_content,
                branch=branch,
            )

            logger.info(
                f"Successfully ingested {repo_full_name}: "
                f"~{digest.estimated_tokens} estimated tokens"
            )
            return digest

        except subprocess.TimeoutExpired:
            logger.error(f"gitingest timed out for repository: {repo_full_name}")
            return None
        except FileNotFoundError:
            logger.error("gitingest CLI not found. Falling back to Python library.")
            # Fall back to Python library
            return self._ingest_with_python_library(
                repo_full_name, branch, max_file_size
            )
        except Exception as e:
            logger.error(f"Failed to ingest repository {repo_full_name}: {e}")
            return None

    def _ingest_with_python_library(
        self,
        repo_full_name: str,
        branch: str | None = None,
        max_file_size: int = MAX_FILE_SIZE,
    ) -> RepositoryDigest | None:
        """
        Fallback: Ingest using the Python library directly.
        """
        from gitingest import ingest

        repo_url = f"https://github.com/{repo_full_name}"

        logger.info(f"Using Python gitingest library for: {repo_full_name}")

        try:
            kwargs = {
                "max_file_size": max_file_size,
                "exclude_patterns": [
                    "node_modules/*",
                    "vendor/*",
                    ".git/*",
                    "__pycache__/*",
                    "dist/*",
                    "build/*",
                    "*.lock",
                    "package-lock.json",
                ],
                "include_gitignored": False,
                "include_submodules": False,
            }

            if self.token:
                kwargs["token"] = self.token
            if branch:
                kwargs["branch"] = branch

            summary, tree, content = ingest(repo_url, **kwargs)

            if not content or not content.strip():
                logger.warning(f"No content from {repo_full_name}")
                return None

            return RepositoryDigest(
                repo_full_name=repo_full_name,
                summary=summary,
                tree=tree,
                content=content,
                branch=branch,
            )

        except Exception as e:
            logger.error(f"Python library failed for {repo_full_name}: {e}")
            return None
