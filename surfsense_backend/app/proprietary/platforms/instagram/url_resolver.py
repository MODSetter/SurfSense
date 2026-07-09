"""Classify and normalize an Instagram URL into a scrape job.

Covers the supported ``directUrls`` shapes: a profile, a post (``/p/``), a reel
(``/reel/``), a hashtag (``/explore/tags/``), and a place
(``/explore/locations/``), plus bare profile IDs. Non-Instagram hosts resolve to
``None`` so the orchestrator can skip them. Mirrors the frozen ``ResolvedUrl``
dataclass shape of ``../reddit/url_resolver.py``.

Normalization rules (from the reference spec):
- ``_u/`` and ``/profilecard/`` segments are stripped.
- Story URLs (``/stories/<user>/...``) reduce to the profile.
- Location URLs are valid with the numeric ID alone (no trailing slug).
- Numeric post-ID URLs are only valid for the ``comments`` flow; elsewhere the
  shortCode form is required, so a numeric-ID URL resolves with
  ``numeric_post_id`` set and callers reject it outside comments.
- ``share/`` redirect resolution is handled at fetch time (network), not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

ResolvedKind = Literal["profile", "post", "reel", "hashtag", "place"]

_INSTAGRAM_HOSTS = frozenset(
    {"m.instagram.com", "www.instagram.com", "instagram.com"}
)
_STRIP_SEGMENTS = frozenset({"_u", "profilecard"})
_RESERVED = frozenset(
    {"p", "s", "tv", "reel", "reels", "share", "explore", "stories", "accounts"}
)


@dataclass(frozen=True)
class ResolvedUrl:
    """A classified Instagram target: the kind, its key, and the source URL."""

    kind: ResolvedKind
    value: str
    url: str
    slug: str | None = None
    numeric_post_id: bool = False


def _is_instagram_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname.lower() in _INSTAGRAM_HOSTS


def _segments(url: str) -> list[str]:
    parsed = urlparse(url)
    if not _is_instagram_host(parsed.hostname):
        return []
    if not parsed.path:
        return []
    return [s for s in parsed.path.split("/") if s and s not in _STRIP_SEGMENTS]


def resolve_url(url: str) -> ResolvedUrl | None:
    """Classify an Instagram URL into a scrape job, or ``None`` if unrecognized.

    A bare token with no ``http`` prefix and no ``/`` is treated as a profile ID
    (the reference accepts bare profile handles alongside full URLs).
    """
    if "instagram.com" not in url.lower():
        token = url.strip().lstrip("@")
        if token and "/" not in token and "." not in token:
            return ResolvedUrl(
                "profile", token, f"https://www.instagram.com/{token}/"
            )
    segments = _segments(url)
    if not segments:
        return None
    head = segments[0]
    if head == "explore" and len(segments) >= 3 and segments[1] == "tags":
        return ResolvedUrl("hashtag", segments[2], url)
    if head == "explore" and len(segments) >= 3 and segments[1] == "locations":
        slug = segments[3] if len(segments) >= 4 else None
        return ResolvedUrl("place", segments[2], url, slug=slug)
    if head == "p" and len(segments) >= 2:
        code = segments[1]
        return ResolvedUrl("post", code, url, numeric_post_id=code.isdigit())
    if head in ("reel", "reels") and len(segments) >= 2:
        code = segments[1]
        return ResolvedUrl("reel", code, url, numeric_post_id=code.isdigit())
    if head == "stories" and len(segments) >= 2:
        user = segments[1]
        return ResolvedUrl(
            "profile", user, f"https://www.instagram.com/{user}/"
        )
    if head not in _RESERVED:
        return ResolvedUrl("profile", head, url)
    return None
