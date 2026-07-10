"""Offline parser tests: raw web JSON -> flat item dicts.

Synthetic nodes cover the GraphQL ``edge_*`` flattening the anonymous web
payloads use. A fixture-pinned test runs only when a captured fixture is present
(the live e2e script dumps trimmed, PII-anonymized fixtures), so the suite stays
green offline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.proprietary.platforms.instagram.parsers import (
    parse_media,
    parse_post,
    parse_profile,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def _edge(nodes: list[dict]) -> dict:
    return {"edges": [{"node": n} for n in nodes]}


def test_parse_media_flattens_edges_and_extracts_tags():
    node = {
        "id": "1",
        "shortcode": "Cabc",
        "__typename": "GraphImage",
        "taken_at_timestamp": 1_600_000_000,
        "edge_media_to_caption": _edge([{"text": "love #nasa shot @buzz"}]),
        "edge_media_to_comment": {"count": 7},
        "edge_liked_by": {"count": 42},
        "owner": {"username": "natgeo", "id": "9"},
    }
    item = parse_media(node)
    assert item["shortCode"] == "Cabc"
    assert item["type"] == "Image"
    assert item["hashtags"] == ["nasa"]
    assert item["mentions"] == ["buzz"]
    assert item["commentsCount"] == 7
    assert item["likesCount"] == 42
    assert item["ownerUsername"] == "natgeo"
    assert item["url"] == "https://www.instagram.com/p/Cabc/"


def test_parse_media_passes_through_hidden_like_count():
    # Instagram reports -1 when the creator hid likes; never coerce it away.
    item = parse_media({"id": "1", "edge_liked_by": {"count": -1}})
    assert item["likesCount"] == -1


def test_parse_media_marks_video_type():
    item = parse_media({"id": "1", "is_video": True, "video_view_count": 99})
    assert item["type"] == "Video"
    assert item["videoViewCount"] == 99


def test_parse_profile_flattens_counts_and_latest_posts():
    user = {
        "id": "9",
        "username": "natgeo",
        "full_name": "Nat Geo",
        "edge_followed_by": {"count": 1000},
        "edge_follow": {"count": 50},
        "edge_owner_to_timeline_media": {
            "count": 2,
            "edges": [{"node": {"id": "p1", "shortcode": "A"}}],
        },
    }
    item = parse_profile(user)
    assert item["detailKind"] == "profile"
    assert item["username"] == "natgeo"
    assert item["followersCount"] == 1000
    assert item["followsCount"] == 50
    assert item["postsCount"] == 2
    assert len(item["latestPosts"]) == 1


_POST_URL = "https://www.instagram.com/p/Cabc/"


def test_parse_post_prefers_ldjson():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type": "VideoObject", "articleBody": "sunset over #bali with @friend",
     "uploadDate": "2024-01-02T03:04:05Z",
     "author": {"@type": "Person", "alternateName": "@natgeo"},
     "video": {"contentUrl": "https://cdn/v.mp4"},
     "image": {"url": "https://cdn/i.jpg"},
     "interactionStatistic": [
       {"interactionType": "https://schema.org/LikeAction", "userInteractionCount": 4200},
       {"interactionType": "https://schema.org/CommentAction", "userInteractionCount": 37}
     ]}
    </script>
    </head></html>
    """
    item = parse_post(html, url=_POST_URL, shortcode="Cabc")
    assert item is not None
    assert item["type"] == "Video"
    assert item["shortCode"] == "Cabc"
    assert item["url"] == _POST_URL
    assert item["ownerUsername"] == "natgeo"
    assert item["caption"] == "sunset over #bali with @friend"
    assert item["hashtags"] == ["bali"]
    assert item["mentions"] == ["friend"]
    assert item["likesCount"] == 4200
    assert item["commentsCount"] == 37
    assert item["videoUrl"] == "https://cdn/v.mp4"
    assert item["timestamp"] == "2024-01-02T03:04:05Z"


def test_parse_post_falls_back_to_og_meta():
    html = """
    <html><head>
    <meta property="og:type" content="video.other" />
    <meta property="og:image" content="https://cdn/i.jpg" />
    <meta property="og:description"
      content="1,234 likes, 56 comments - natgeo on January 2, 2024: &quot;a caption&quot;" />
    </head></html>
    """
    item = parse_post(html, url=_POST_URL, shortcode="Cabc")
    assert item is not None
    assert item["likesCount"] == 1234
    assert item["commentsCount"] == 56
    assert item["displayUrl"] == "https://cdn/i.jpg"
    assert item["type"] == "Video"


def test_parse_post_returns_none_without_surfaces():
    # A login interstitial / empty doc carries neither ld+json nor og -> None,
    # never a silent empty-success item.
    assert parse_post("<html><body>login</body></html>", url=_POST_URL) is None
    assert parse_post(None, url=_POST_URL) is None
    assert parse_post("", url=_POST_URL) is None


@pytest.mark.skipif(
    not (_FIXTURES / "profile.json").exists(),
    reason="captured fixture absent (run scripts/e2e_instagram_scraper.py to dump)",
)
def test_fixture_profile_maps():
    raw = json.loads((_FIXTURES / "profile.json").read_text())
    user = raw.get("data", {}).get("user", raw)
    item = parse_profile(user)
    assert item["detailKind"] == "profile"
    assert item["username"]


@pytest.mark.skipif(
    not (_FIXTURES / "post.json").exists(),
    reason="captured fixture absent (run the single-post probe to dump /p/ HTML)",
)
def test_fixture_post_maps():
    raw = json.loads((_FIXTURES / "post.json").read_text())
    item = parse_post(raw["html"], url=raw["url"], shortcode=raw.get("shortcode"))
    assert item is not None, "captured /p/ HTML produced no media item"
    assert item["url"] == raw["url"]
