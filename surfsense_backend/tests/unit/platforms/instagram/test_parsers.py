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
    parse_comment,
    parse_hashtag,
    parse_media,
    parse_place,
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


def test_parse_comment():
    node = {
        "id": "c1",
        "text": "nice",
        "created_at": 1_600_000_000,
        "shortcode": "Cabc",
        "owner": {"username": "bob", "id": "5"},
        "edge_liked_by": {"count": 3},
    }
    item = parse_comment(node, post_url="https://www.instagram.com/p/Cabc/")
    assert item["id"] == "c1"
    assert item["text"] == "nice"
    assert item["ownerUsername"] == "bob"
    assert item["likesCount"] == 3
    assert item["postUrl"] == "https://www.instagram.com/p/Cabc/"


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


def test_parse_hashtag():
    data = {
        "data": {
            "id": "h1",
            "name": "crossfit",
            "edge_hashtag_to_media": {
                "count": 5,
                "edges": [{"node": {"id": "m1", "shortcode": "A"}}],
            },
            "edge_hashtag_to_top_posts": {
                "edges": [{"node": {"id": "t1", "shortcode": "B"}}]
            },
        }
    }
    item = parse_hashtag(data)
    assert item["detailKind"] == "hashtag"
    assert item["name"] == "crossfit"
    assert item["postsCount"] == 5
    assert len(item["topPosts"]) == 1
    assert len(item["posts"]) == 1


def test_parse_place():
    data = {
        "location": {
            "id": "7538318",
            "name": "Copenhagen",
            "slug": "copenhagen",
            "edge_location_to_media": {
                "count": 3,
                "edges": [{"node": {"id": "m1", "shortcode": "A"}}],
            },
        }
    }
    item = parse_place(data)
    assert item["detailKind"] == "place"
    assert item["name"] == "Copenhagen"
    assert item["location_id"] == "7538318"
    assert len(item["posts"]) == 1


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
