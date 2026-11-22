"""Scrape-target value object produced by URL classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TargetKind = Literal["video", "profile", "hashtag", "search", "trending"]
SearchSection = Literal["video", "user"]


@dataclass(frozen=True, slots=True)
class TikTokTarget:
    """One classified scrape target.

    ``value`` holds the kind-specific identifier: video id, username, hashtag
    name, or search query. ``username`` is set for videos (needed to build the
    canonical post URL). ``section`` narrows a search to videos or users.
    """

    kind: TargetKind
    value: str
    url: str
    username: str | None = None
    section: SearchSection | None = None
