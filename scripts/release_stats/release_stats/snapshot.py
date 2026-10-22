"""One day's snapshot: every asset count, and traffic when the token allows."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from .github_api import GitHubAccessDeniedError, GitHubApi
from .release_assets import AssetCount, read_asset_counts
from .repo_traffic import Traffic, read_traffic


class Snapshot(TypedDict):
    taken_at: str
    repo: str
    assets: list[AssetCount]
    traffic: Traffic | None
    traffic_skipped: str | None


def take_snapshot(api: GitHubApi, repo: str, now: datetime) -> Snapshot:
    traffic: Traffic | None = None
    skipped: str | None = None
    try:
        traffic = read_traffic(api, repo)
    except GitHubAccessDeniedError as denied:
        # Asset counts are public, so a token without push access still
        # yields the half of the snapshot that matters most.
        skipped = f"token cannot read traffic ({denied})"
    return Snapshot(
        taken_at=now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        repo=repo,
        assets=read_asset_counts(api, repo),
        traffic=traffic,
        traffic_skipped=skipped,
    )
