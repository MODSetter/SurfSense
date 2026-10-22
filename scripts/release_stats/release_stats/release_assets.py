"""Every published release's asset download counts, as flat rows."""

from __future__ import annotations

from typing import Any, TypedDict

from .asset_kinds import AssetKind, asset_kind
from .github_api import GitHubApi


class AssetCount(TypedDict):
    tag: str
    asset: str
    kind: AssetKind
    download_count: int
    published_at: str
    prerelease: bool


def read_asset_counts(api: GitHubApi, repo: str) -> list[AssetCount]:
    rows: list[AssetCount] = []
    for page in api.pages(f"repos/{repo}/releases?per_page=100"):
        for release in page:
            rows.extend(asset_counts_of(release))
    return rows


def asset_counts_of(release: dict[str, Any]) -> list[AssetCount]:
    # A draft has no publish time and only maintainers can download it.
    if release.get("draft") or not release.get("published_at"):
        return []
    return [
        AssetCount(
            tag=str(release["tag_name"]),
            asset=str(asset["name"]),
            kind=asset_kind(str(asset["name"])),
            download_count=int(asset.get("download_count") or 0),
            published_at=str(release["published_at"]),
            prerelease=bool(release.get("prerelease")),
        )
        for asset in release.get("assets") or []
    ]
