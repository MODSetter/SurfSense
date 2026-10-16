"""Fields the parsers used to drop or misread, on scrubbed live captures (no network).

``explore_item.json`` is one itemStruct from the live Explore feed (signed URL
queries stripped, the creator replaced); ``user_search_list.json`` keeps the verification fields of a
live ``/api/search/user/full/`` body.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from proprietary.tiktok.extraction import (
    parse_search_user,
    parse_video,
    users_from_response,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_video_keeps_language_and_ad_flag():
    item = parse_video(_fixture("explore_item.json"))

    assert item["id"] == "7695439183640349985"
    assert item["textLanguage"] == "en"
    assert item["isAd"] is False
    assert item["isSlideshow"] is False
    assert item["mediaUrls"] == []  # a video's playAddr expires, so none is kept
    assert item["isPinned"] is None  # only profile listings carry isPinnedItem


def test_explore_capture_keeps_no_creator_identity():
    # The creator is a private person: the capture keeps stand-ins only.
    author = parse_video(_fixture("explore_item.json"))["authorMeta"]

    assert (author["id"], author["name"], author["nickName"]) == (
        "1",
        "creator",
        "Creator",
    )
    assert author["signature"] == "bio"
    assert author["profileUrl"] == "https://www.tiktok.com/@creator"


def test_parse_video_maps_mentions_from_text_extra():
    raw = copy.deepcopy(_fixture("explore_item.json"))
    raw["textExtra"] = [
        {"type": 1, "hashtagName": "fy"},
        {"type": 0, "userUniqueId": "lil.kam", "userId": "1"},
        {"type": 0, "userUniqueId": ""},
        "not a dict",
    ]

    assert parse_video(raw)["mentions"] == ["lil.kam"]


def test_parse_video_maps_pinned_and_slideshow_images():
    raw = copy.deepcopy(_fixture("explore_item.json"))
    raw["isPinnedItem"] = True
    raw["imagePost"] = {
        "images": [
            {"imageURL": {"urlList": ["https://cdn/a.jpeg", "https://cdn/a2.jpeg"]}},
            {"imageURL": {"urlList": []}},
            {"imageURL": {"urlList": ["https://cdn/b.jpeg"]}},
        ]
    }

    item = parse_video(raw)

    assert item["isPinned"] is True
    assert item["isSlideshow"] is True
    assert item["mediaUrls"] == ["https://cdn/a.jpeg", "https://cdn/b.jpeg"]


def test_user_search_reads_only_the_badge_as_verified():
    users = users_from_response(_fixture("user_search_list.json"))
    verified = {u["unique_id"]: parse_search_user(u)["verified"] for u in users}

    assert verified == {
        "espnfc": True,
        "espn": True,
        "espnuk": True,
        "espndeutschland": False,  # "Business account" is not a badge
    }


def test_user_search_custom_verify_counts_as_verified():
    user = {"unique_id": "x", "custom_verify": "Official account"}

    assert parse_search_user(user)["verified"] is True
