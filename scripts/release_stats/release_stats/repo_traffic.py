"""The repository's traffic, which GitHub keeps for 14 days only.

These endpoints need push access, which ``GITHUB_TOKEN`` never has.
"""

from __future__ import annotations

from typing import Any, TypedDict

from .github_api import GitHubApi


class Traffic(TypedDict):
    views: dict[str, Any]
    clones: dict[str, Any]
    referrers: list[dict[str, Any]]
    paths: list[dict[str, Any]]


def read_traffic(api: GitHubApi, repo: str) -> Traffic:
    """Raises ``GitHubAccessDeniedError`` when the token lacks push access."""
    base = f"repos/{repo}/traffic"
    return Traffic(
        views=api.get(f"{base}/views"),
        clones=api.get(f"{base}/clones"),
        referrers=api.get(f"{base}/popular/referrers"),
        paths=api.get(f"{base}/popular/paths"),
    )
