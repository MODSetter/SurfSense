"""
GitHub connector using gitingest for efficient repository digestion.

This connector replaces the previous file-by-file approach with a single
digest generation per repository, dramatically reducing LLM API calls.
"""

import logging
from dataclasses import dataclass

from gitingest import ingest_async

logger = logging.getLogger(__name__)

# Maximum file size in bytes (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024

# Default patterns to exclude (recommended approach for comprehensive analysis)
# Using only exclude_patterns ensures we don't miss any relevant file types
DEFAULT_EXCLUDE_PATTERNS = [
    # Dependencies
    "node_modules/*",
    "vendor/*",
    "bower_components/*",
    ".pnpm/*",
    # Build artifacts / Caches
    "build/*",
    "dist/*",
    "target/*",
    "out/*",
    "__pycache__/*",
    "*.pyc",
    ".cache/*",
    ".next/*",
    ".nuxt/*",
    # Virtual environments
    "venv/*",
    ".venv/*",
    "env/*",
    ".env/*",
    # IDE/Editor config
    ".vscode/*",
    ".idea/*",
    ".project",
    ".settings/*",
    "*.swp",
    "*.swo",
    # Version control
    ".git/*",
    ".svn/*",
    ".hg/*",
    # Temporary / Logs
    "tmp/*",
    "temp/*",
    "logs/*",
    "*.log",
    # Lock files (usually not needed for understanding code)
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "Gemfile.lock",
    "poetry.lock",
    "Cargo.lock",
    "composer.lock",
    # Binary/media files
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.svg",
    "*.webp",
    "*.bmp",
    "*.tiff",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.otf",
    "*.mp3",
    "*.mp4",
    "*.wav",
    "*.ogg",
    "*.webm",
    "*.avi",
    "*.mov",
    "*.pdf",
    "*.doc",
    "*.docx",
    "*.xls",
    "*.xlsx",
    "*.ppt",
    "*.pptx",
    "*.zip",
    "*.tar",
    "*.tar.gz",
    "*.tgz",
    "*.rar",
    "*.7z",
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    "*.bin",
    "*.obj",
    "*.o",
    "*.a",
    "*.lib",
    # Minified files
    "*.min.js",
    "*.min.css",
    # Source maps
    "*.map",
    # Database files
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    # Coverage reports
    "coverage/*",
    ".coverage",
    "htmlcov/*",
    ".nyc_output/*",
    # Test snapshots (can be large)
    "__snapshots__/*",
]


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
    Connector for ingesting GitHub repositories using gitingest.

    This connector efficiently processes entire repositories into a single
    digest, reducing the number of API calls and LLM invocations compared
    to file-by-file processing.
    """

    def __init__(self, token: str | None = None):
        """
        Initializes the GitHub connector.

        Args:
            token: Optional GitHub Personal Access Token (PAT).
                   Only required for private repositories.
                   Public repositories can be ingested without a token.
        """
        self.token = token if token and token.strip() else None
        if self.token:
            logger.info("GitHub connector initialized with authentication token.")
        else:
            logger.info("GitHub connector initialized without token (public repos only).")

    async def ingest_repository(
        self,
        repo_full_name: str,
        branch: str | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        max_file_size: int = MAX_FILE_SIZE,
    ) -> RepositoryDigest | None:
        """
        Ingest an entire repository and return a digest.

        Args:
            repo_full_name: The full name of the repository (e.g., 'owner/repo').
            branch: Optional specific branch or tag to ingest.
            include_patterns: Optional list of glob patterns for files to include.
                             If None, includes all files (recommended).
            exclude_patterns: Optional list of glob patterns for files to exclude.
                             If None, uses DEFAULT_EXCLUDE_PATTERNS.
            max_file_size: Maximum file size in bytes to include (default 5MB).

        Returns:
            RepositoryDigest containing the summary, tree structure, and content,
            or None if ingestion fails.
        """
        repo_url = f"https://github.com/{repo_full_name}"

        # Use only exclude_patterns by default (recommended for comprehensive analysis)
        # This ensures we don't miss any relevant file types
        exclude_pats = exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDE_PATTERNS

        logger.info(f"Starting gitingest for repository: {repo_full_name}")

        try:
            # Build kwargs dynamically
            ingest_kwargs = {
                "max_file_size": max_file_size,
                "exclude_patterns": exclude_pats,
                "include_gitignored": False,
                "include_submodules": False,
            }

            # Only add token if provided (required only for private repos)
            if self.token:
                ingest_kwargs["token"] = self.token

            # Only add branch if specified
            if branch:
                ingest_kwargs["branch"] = branch

            # Only add include_patterns if explicitly provided
            if include_patterns is not None:
                ingest_kwargs["include_patterns"] = include_patterns

            summary, tree, content = await ingest_async(repo_url, **ingest_kwargs)

            if not content or not content.strip():
                logger.warning(
                    f"No content retrieved from repository: {repo_full_name}"
                )
                return None

            digest = RepositoryDigest(
                repo_full_name=repo_full_name,
                summary=summary,
                tree=tree,
                content=content,
                branch=branch,
            )

            logger.info(
                f"Successfully ingested {repo_full_name}: "
                f"~{digest.estimated_tokens} estimated tokens"
            )
            return digest

        except Exception as e:
            logger.error(f"Failed to ingest repository {repo_full_name}: {e}")
            return None

    async def ingest_repositories(
        self,
        repo_full_names: list[str],
        branch: str | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        max_file_size: int = MAX_FILE_SIZE,
    ) -> list[RepositoryDigest]:
        """
        Ingest multiple repositories and return their digests.

        Args:
            repo_full_names: List of repository full names (e.g., ['owner/repo1', 'owner/repo2']).
            branch: Optional specific branch or tag to ingest (applied to all repos).
            include_patterns: Optional list of glob patterns for files to include.
            exclude_patterns: Optional list of glob patterns for files to exclude.
            max_file_size: Maximum file size in bytes to include.

        Returns:
            List of RepositoryDigest objects for successfully ingested repositories.
        """
        digests = []

        for repo_full_name in repo_full_names:
            if not repo_full_name or not isinstance(repo_full_name, str):
                logger.warning(f"Skipping invalid repository entry: {repo_full_name}")
                continue

            digest = await self.ingest_repository(
                repo_full_name=repo_full_name,
                branch=branch,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                max_file_size=max_file_size,
            )

            if digest:
                digests.append(digest)

        logger.info(
            f"Ingested {len(digests)} out of {len(repo_full_names)} repositories."
        )
        return digests
