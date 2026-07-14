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


def test_parse_media_extracts_sidecar_tags_location_pinned():
    # The anonymous profile feed node carries far more than the core fields:
    # sidecar children, tagged users, coauthors, location, product type and pin
    # state — all populated here from the real GraphQL key shapes.
    node = {
        "id": "1",
        "shortcode": "Cabc",
        "__typename": "GraphSidecar",
        "taken_at_timestamp": 1_704_164_645,
        "edge_media_to_caption": _edge([{"text": "x #tag @me"}]),
        "pinned_for_users": [{"id": "9"}],
        "product_type": "feed",
        "location": {"id": "55", "name": "Paris"},
        "coauthor_producers": [{"username": "co", "id": "7"}],
        "edge_media_to_tagged_user": _edge(
            [{"user": {"username": "tg", "id": "3"}, "x": 0.1, "y": 0.2}]
        ),
        "edge_sidecar_to_children": _edge(
            [
                {
                    "id": "c1",
                    "shortcode": "s1",
                    "display_url": "https://cdn/1.jpg",
                    "dimensions": {"height": 10, "width": 20},
                },
                {
                    "id": "c2",
                    "shortcode": "s2",
                    "is_video": True,
                    "video_url": "https://cdn/2.mp4",
                    "display_url": "https://cdn/2.jpg",
                },
            ]
        ),
    }
    item = parse_media(node)
    assert item["type"] == "Sidecar"
    assert item["isPinned"] is True
    assert item["productType"] == "feed"
    assert item["locationName"] == "Paris"
    assert item["locationId"] == "55"
    assert item["taggedUsers"][0]["username"] == "tg"
    assert item["coauthorProducers"][0]["username"] == "co"
    assert item["images"] == ["https://cdn/1.jpg", "https://cdn/2.jpg"]
    assert len(item["childPosts"]) == 2
    assert item["childPosts"][1]["type"] == "Video"
    assert item["childPosts"][1]["videoUrl"] == "https://cdn/2.mp4"


def test_parse_media_unpinned_is_false():
    assert parse_media({"id": "1"})["isPinned"] is False


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
        "edge_related_profiles": _edge(
            [{"username": "similar1", "id": "11"}, {"username": "similar2", "id": "12"}]
        ),
    }
    item = parse_profile(user)
    assert item["detailKind"] == "profile"
    assert item["username"] == "natgeo"
    assert item["followersCount"] == 1000
    assert item["followsCount"] == 50
    assert item["postsCount"] == 2
    assert len(item["latestPosts"]) == 1
    assert [p["username"] for p in item["relatedProfiles"]] == ["similar1", "similar2"]


_POST_URL = "https://www.instagram.com/p/Cabc/"


def test_parse_post_prefers_relay_json():
    # Anonymous /p/ pages inline the mobile-v1 PolarisMedia object in an
    # application/json script. It's the full-fidelity source (carousel children,
    # tagged users, coauthors, location, precise timestamp), preferred over og.
    media = {
        "pk": "3938367641542741384",
        "id": "POLARIS_3938367641542741384",
        "code": "Cabc",
        "taken_at": 1_704_164_645,
        "media_type": 8,
        "product_type": "carousel_container",
        "like_count": 4200,
        "comment_count": 37,
        "accessibility_caption": "alt text",
        "caption": {"text": "sunset over #bali with @friend @friend"},
        "user": {"username": "natgeo", "full_name": "Nat Geo", "id": "9"},
        "image_versions2": {"candidates": [{"url": "https://cdn/i.jpg"}]},
        "carousel_media": [
            {
                "id": "m1",
                "code": "c1",
                "media_type": 1,
                "image_versions2": {"candidates": [{"url": "https://cdn/c1.jpg"}]},
                "original_height": 1080,
                "original_width": 1080,
            },
            {
                "id": "m2",
                "code": "c2",
                "media_type": 2,
                "video_versions": [{"url": "https://cdn/c2.mp4"}],
                "image_versions2": {"candidates": [{"url": "https://cdn/c2.jpg"}]},
            },
        ],
        "usertags": {
            "in": [
                {"position": [0.5, 0.5], "user": {"username": "tagged1", "id": "77"}}
            ]
        },
        "coauthor_producers": [
            {"username": "coauthor1", "id": "88", "is_verified": True}
        ],
        "location": {"id": "123", "name": "Bali"},
    }
    html = (
        '<html><body><script type="application/json" data-sjs>'
        + json.dumps({"a": {"b": [{"items": [media]}]}})
        + "</script></body></html>"
    )
    item = parse_post(html, url=_POST_URL, shortcode="Cabc")
    assert item is not None
    assert item["id"] == "3938367641542741384"  # POLARIS_ prefix stripped
    assert item["type"] == "Sidecar"  # media_type 8
    assert item["shortCode"] == "Cabc"
    assert item["url"] == _POST_URL
    assert item["caption"] == "sunset over #bali with @friend @friend"
    assert item["hashtags"] == ["bali"]
    assert item["mentions"] == ["friend"]  # deduped
    assert item["likesCount"] == 4200
    assert item["commentsCount"] == 37
    assert item["displayUrl"] == "https://cdn/i.jpg"
    assert item["timestamp"].startswith("2024-01-02T")  # real epoch -> ISO w/ time
    assert item["ownerUsername"] == "natgeo"
    assert item["ownerFullName"] == "Nat Geo"
    assert item["images"] == ["https://cdn/c1.jpg", "https://cdn/c2.jpg"]
    assert len(item["childPosts"]) == 2
    assert item["childPosts"][1]["type"] == "Video"
    assert item["childPosts"][1]["videoUrl"] == "https://cdn/c2.mp4"
    assert item["taggedUsers"][0]["username"] == "tagged1"
    assert item["coauthorProducers"][0]["username"] == "coauthor1"
    assert item["locationName"] == "Bali"
    assert item["locationId"] == "123"
    assert item["productType"] == "carousel_container"


def test_parse_post_falls_back_to_og_meta():
    # Anonymous /p/ pages carry no ld+json; everything is lifted from the og
    # tags. og:description gives counts + username + date; og:title gives the
    # clean caption + full name. Entities in the caption are deduped.
    html = """
    <html><head>
    <meta property="og:type" content="video.other" />
    <meta property="og:image" content="https://cdn/i.jpg" />
    <meta property="al:ios:url" content="instagram://media?id=3938367641542741384" />
    <meta property="og:title"
      content="Nat Geo on Instagram: &quot;a caption #wow #wow &#064;buzz.&quot;" />
    <meta property="og:description"
      content="1,234 likes, 56 comments - natgeo on January 2, 2024: &quot;a caption #wow #wow &#064;buzz.&quot;" />
    </head></html>
    """
    item = parse_post(html, url=_POST_URL, shortcode="Cabc")
    assert item is not None
    assert item["id"] == "3938367641542741384"  # numeric pk from al:ios:url meta
    assert item["likesCount"] == 1234
    assert item["commentsCount"] == 56
    assert item["displayUrl"] == "https://cdn/i.jpg"
    assert item["type"] == "Video"
    assert item["ownerUsername"] == "natgeo"
    assert item["ownerFullName"] == "Nat Geo"
    assert item["timestamp"] == "2024-01-02"  # og carries date only, no time
    assert item["caption"] == "a caption #wow #wow @buzz."  # &#064; -> @, unescaped
    assert item["hashtags"] == ["wow"]  # deduped, no &#064;-as-#064 pollution
    assert item["mentions"] == ["buzz"]  # trailing sentence dot stripped


def test_parse_post_og_degrades_without_crashing():
    # A shape we don't recognise (hidden likes / a non-English locale that
    # slipped the en-US header) must yield a partial item with None fields,
    # never an exception or a caption polluted with the counts/date prefix.
    html = """
    <html><head>
    <meta property="og:type" content="article" />
    <meta property="og:image" content="https://cdn/i.jpg" />
    <meta property="og:title" content="Nat Geo no Instagram: &quot;ol\u00e1&quot;" />
    <meta property="og:description" content="alguma coisa sem formato" />
    </head></html>
    """
    item = parse_post(html, url=_POST_URL, shortcode="Cabc")
    assert item is not None  # og:image present -> still emits
    assert item["displayUrl"] == "https://cdn/i.jpg"
    assert item["likesCount"] is None
    assert item["commentsCount"] is None
    assert item["ownerUsername"] is None
    assert item["timestamp"] is None
    assert item["caption"] is None  # unrecognised prefix -> no pollution


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
    # The relay blob (not og-meta) should drive extraction: numeric id + a
    # precise timestamp with a time component (og-only would be date-only).
    assert item["id"] and item["id"].isdigit()
    assert item["ownerUsername"]
    assert item["timestamp"] and "T" in item["timestamp"]
