"""Offline parser tests for the Reddit scraper.

Two layers:
- Synthetic, deterministic checks of the JSON->item mapping (hand-built minimal
  "things" — no live Reddit shapes), which run always.
- Fixture-pinned checks against real ``.json`` captured by
  ``scripts/e2e_reddit_scraper.py`` into ``fixtures/``; these ``skip`` when the
  fixtures are absent (mirrors the youtube sibling). Fill in richer assertions
  against the captured shapes during implementation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.proprietary.platforms.reddit.parsers import (
    after,
    children,
    flatten_comments,
    parse_comment,
    parse_community,
    parse_post,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


# --- synthetic mapping (always runs) ---------------------------------------


def test_parse_post_maps_core_fields():
    thing = {
        "kind": "t3",
        "data": {
            "name": "t3_x",
            "id": "x",
            "author": "alice",
            "author_fullname": "t2_a",
            "title": "Hello",
            "selftext": "body text",
            "permalink": "/r/py/comments/x/hello/",
            "subreddit": "py",
            "subreddit_name_prefixed": "r/py",
            "num_comments": 3,
            "score": 42,
            "upvote_ratio": 0.97,
            "over_18": False,
            "is_self": True,
            "created_utc": 1_700_000_000,
            "thumbnail": "self",
        },
    }
    item = parse_post(thing)
    assert item["dataType"] == "post"
    assert item["id"] == "t3_x"
    assert item["parsedId"] == "x"
    assert item["url"] == "https://www.reddit.com/r/py/comments/x/hello/"
    assert item["upVotes"] == 42
    assert item["numberOfComments"] == 3
    assert item["thumbnailUrl"] is None  # 'self' sentinel is not a URL
    assert item["createdAt"] == "2023-11-14T22:13:20.000Z"


def test_parse_comment_strips_link_prefix():
    thing = {
        "kind": "t1",
        "data": {
            "name": "t1_c",
            "id": "c",
            "body": "a comment",
            "link_id": "t3_x",
            "parent_id": "t3_x",
            "created_utc": 1_700_000_000,
        },
    }
    item = parse_comment(thing)
    assert item["dataType"] == "comment"
    assert item["postId"] == "x"  # t3_ prefix stripped
    assert item["parentId"] == "t3_x"


def test_flatten_comments_counts_replies_and_stops_at_more():
    tree = [
        {
            "kind": "t1",
            "data": {
                "name": "t1_1",
                "id": "1",
                "body": "top",
                "created_utc": 1,
                "replies": {
                    "kind": "Listing",
                    "data": {
                        "children": [
                            {
                                "kind": "t1",
                                "data": {
                                    "name": "t1_2",
                                    "id": "2",
                                    "body": "reply",
                                    "replies": "",
                                },
                            },
                            {"kind": "more", "data": {}},  # stub -> ignored
                        ]
                    },
                },
            },
        }
    ]
    flat = flatten_comments(tree, max_comments=10)
    assert len(flat) == 2  # the 'more' stub is skipped
    assert flat[0]["numberOfReplies"] == 1
    assert [c["depth"] for c in flat] == [0, 1]


def test_flatten_comments_honors_max():
    tree = [
        {
            "kind": "t1",
            "data": {"name": f"t1_{i}", "id": str(i), "body": "x", "replies": ""},
        }
        for i in range(5)
    ]
    assert len(flatten_comments(tree, max_comments=2)) == 2


def test_children_and_after():
    listing = {"kind": "Listing", "data": {"children": [1, 2, 3], "after": "t3_next"}}
    assert children(listing) == [1, 2, 3]
    assert after(listing) == "t3_next"
    assert children({}) == []
    assert after({"data": {"after": None}}) is None


def test_parse_community_maps_members():
    thing = {
        "kind": "t5",
        "data": {
            "name": "t5_s",
            "id": "s",
            "display_name": "py",
            "display_name_prefixed": "r/py",
            "subscribers": 1234,
            "url": "/r/py/",
        },
    }
    item = parse_community(thing)
    assert item["dataType"] == "community"
    assert item["numberOfMembers"] == 1234
    assert item["url"] == "https://www.reddit.com/r/py/"


# --- fixture-pinned (skips until e2e captures real .json) ------------------


def _load(name: str):
    path = _FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"fixture {name} not captured yet (run e2e_reddit_scraper.py)")
    return json.loads(path.read_text(encoding="utf-8"))


def test_parse_captured_post_fixture_if_present():
    data = _load("sample_post.json")
    # sample_post.json is the [postListing, commentsListing] .json shape.
    post_children = children(data[0]) if isinstance(data, list) else []
    assert post_children, "captured post fixture has no post child"
    item = parse_post(post_children[0])
    assert item["dataType"] == "post"
    assert item["id"]


def test_parse_captured_listing_fixture_if_present():
    listing = _load("sample_listing.json")
    kids = children(listing)
    assert kids, "captured listing fixture is empty"
    posts = [parse_post(c) for c in kids if c.get("kind") == "t3"]
    assert posts, "no t3 posts in captured listing"
