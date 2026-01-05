"""GitHub connector using gitingest for bulk repository processing."""

import logging
from typing import Any

from github3 import exceptions as github_exceptions
from github3 import login as github_login
from github3.exceptions import ForbiddenError

from .gitingest_service import GitIngestService

logger = logging.getLogger(__name__)


class GitHubConnectorGitingest:
    """GitHub connector using gitingest for bulk repository processing."""

    def __init__(self, token: str):
        if not token:
            raise ValueError("GitHub token cannot be empty.")

        try:
            self.gh = github_login(token=token)
            self.gh.me()
            logger.info("Successfully authenticated with GitHub API.")
        except (github_exceptions.AuthenticationFailed, ForbiddenError) as e:
            logger.error(f"GitHub authentication failed: {e}")
            raise ValueError("Invalid GitHub token or insufficient permissions.") from e
        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {e}")
            raise e

        self.gitingest = GitIngestService(token=token)
        self.token = token

    def get_user_repositories(self) -> list[dict[str, Any]]:
        """Fetch repositories accessible by the authenticated user."""
        repos_data = []
        try:
            for repo in self.gh.repositories(type="all", sort="updated"):
                repos_data.append(
                    {
                        "id": repo.id,
                        "name": repo.name,
                        "full_name": repo.full_name,
                        "private": repo.private,
                        "url": repo.html_url,
                        "description": repo.description or "",
                        "last_updated": repo.updated_at if repo.updated_at else None,
                        "default_branch": repo.default_branch or "main",
                    }
                )
            logger.info(f"Fetched {len(repos_data)} repositories.")
            return repos_data
        except Exception as e:
            logger.error(f"Failed to fetch GitHub repositories: {e}")
            return []

    def process_repository(self, repo_full_name: str) -> dict[str, Any]:
        """Process a repository using gitingest and return content with metadata."""
        try:
            owner, repo_name = repo_full_name.split("/")
            repo = self.gh.repository(owner, repo_name)

            if not repo:
                raise ValueError(f"Repository '{repo_full_name}' not found.")

            branch = repo.default_branch or "main"
            repo_url = f"https://github.com/{repo_full_name}"

            logger.info(f"Processing repository {repo_full_name} (branch: {branch})")

            result = self.gitingest.process_repository(repo_url, branch)

            result["metadata"].update(
                {
                    "repo_id": repo.id,
                    "private": repo.private,
                    "description": repo.description or "",
                    "stars": repo.stargazers_count or 0,
                    "language": repo.language or "Unknown",
                    "html_url": repo.html_url,
                }
            )

            logger.info(
                f"Successfully processed {repo_full_name}: {len(result['content'])} characters"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to process repository {repo_full_name}: {e}")
            raise ValueError(f"Failed to process {repo_full_name}: {e!s}") from e

    def process_multiple_repositories(
        self, repo_full_names: list[str]
    ) -> dict[str, Any]:
        """Process multiple repositories and return results with errors."""
        results = {}
        errors = {}

        for repo_full_name in repo_full_names:
            try:
                result = self.process_repository(repo_full_name)
                results[repo_full_name] = result
                logger.info(f"✓ Successfully processed {repo_full_name}")
            except Exception as e:
                errors[repo_full_name] = str(e)
                logger.error(f"✗ Failed to process {repo_full_name}: {e}")

        logger.info(
            f"Processed {len(results)}/{len(repo_full_names)} repositories successfully"
        )

        return {
            "results": results,
            "errors": errors,
            "success_count": len(results),
            "error_count": len(errors),
            "total": len(repo_full_names),
        }

