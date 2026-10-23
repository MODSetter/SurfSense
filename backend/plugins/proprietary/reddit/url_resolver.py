"""Classify a Reddit URL into a scrape job.

Covers the supported ``startUrls`` shapes: a post (permalink), a
subreddit listing, a user profile, and a search-results page. Non-Reddit hosts
resolve to ``None`` so the orchestrator can skip them. Mirrors the frozen
``ResolvedUrl`` dataclass shape of ``../youtube/url_resolver.py``, widened with
the extra context Reddit flows need (subreddit, sort, user content type).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse

ResolvedKind = Literal["post", "subreddit", "user", "search"]
UserContent = Literal["overview", "submitted", "comments"]

_REDDIT_HOSTS = frozenset(
    {
        "reddit.com",
        "www.reddit.com",
        "old.reddit.com",
        "new.reddit.com",
        "np.reddit.com",
        "m.reddit.com",
    }
)

# Listing sorts that can appear as a trailing subreddit path segment.
_SUBREDDIT_SORTS = frozenset({"hot", "new", "top", "rising", "controversial", "best"})
_USER_CONTENT = frozenset({"overview", "submitted", "comments"})


@dataclass(frozen=True)
class ResolvedUrl:
    kind: ResolvedKind
    value: str  # post id, subreddit, username, or search query
    url: str
    subreddit: str | None = None  # carried for posts and in-sub searches
    sort: str | None = None  # trailing subreddit sort, if present
    content: UserContent | None = None  # user profile tab


def _is_reddit_host(hostname: str | None) -> bool:
    return bool(hostname) and hostname.lower() in _REDDIT_HOSTS


def resolve_url(url: str) -> ResolvedUrl | None:
    """Classify a Reddit URL into a scrape job, or ``None`` if unrecognized."""
    parsed = urlparse(url)
    if not _is_reddit_host(parsed.hostname):
        return None

    segments = [s for s in (parsed.path or "").split("/") if s]

    # Search: /search?q=... or /r/<sub>/search?q=...
    if segments and segments[-1] == "search":
        query = parse_qs(parsed.query).get("q", [None])[0]
        if not query:
            return None
        sub = segments[1] if len(segments) >= 3 and segments[0] == "r" else None
        return ResolvedUrl("search", unquote(query), url, subreddit=sub)

    # Subreddit-scoped URLs: /r/<sub>/...
    if len(segments) >= 2 and segments[0] == "r":
        sub = segments[1]
        # Post permalink: /r/<sub>/comments/<id>[/slug]
        if len(segments) >= 4 and segments[2] == "comments":
            return ResolvedUrl("post", segments[3], url, subreddit=sub)
        # Subreddit listing, optional trailing sort: /r/<sub>[/<sort>]
        sort = (
            segments[2]
            if len(segments) >= 3 and segments[2] in _SUBREDDIT_SORTS
            else None
        )
        return ResolvedUrl("subreddit", sub, url, sort=sort)

    # User profile: /user/<name>[/tab] or /u/<name>[/tab]
    if len(segments) >= 2 and segments[0] in ("user", "u"):
        name = segments[1]
        content: UserContent | None = None
        if len(segments) >= 3 and segments[2] in _USER_CONTENT:
            content = segments[2]  # type: ignore[assignment]
        return ResolvedUrl("user", name, url, content=content)

    return None
