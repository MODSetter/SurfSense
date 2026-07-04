"""Offline schema + URL-resolver tests for the Reddit scraper.

Deterministic (no network, no live Reddit shapes): asserts the anonymous-only
input surface, the flat item serialization contract, and URL classification.
"""

from __future__ import annotations

from app.proprietary.scrapers.reddit.schemas import RedditItem, RedditScrapeInput
from app.proprietary.scrapers.reddit.url_resolver import resolve_url


def test_input_has_no_auth_fields():
    # Anonymous-only: no auth-shaped field may exist on the input surface.
    forbidden = {"username", "password", "token", "login", "auth", "credentials"}
    assert forbidden.isdisjoint(RedditScrapeInput.model_fields)


def test_input_defaults():
    model = RedditScrapeInput()
    assert model.sort == "new"
    assert model.includeNSFW is True
    assert model.maxItems == 10
    assert model.startUrls == []
    assert model.searches == []


def test_input_allows_extra_inert_fields():
    # extra="allow": Apify fields we don't act on are accepted, not rejected.
    model = RedditScrapeInput(debugMode=True, proxy={"useApifyProxy": True})
    assert model.model_dump().get("debugMode") is True


def test_item_to_output_keeps_none_keys():
    out = RedditItem(dataType="post", id="t3_x").to_output()
    assert out["dataType"] == "post"
    assert out["id"] == "t3_x"
    assert "numberOfComments" in out  # unsourced fields still present (None)
    assert out["numberOfComments"] is None


def test_resolve_post():
    r = resolve_url("https://www.reddit.com/r/python/comments/abc123/some_title/")
    assert r is not None
    assert r.kind == "post"
    assert r.value == "abc123"
    assert r.subreddit == "python"


def test_resolve_subreddit_with_and_without_sort():
    bare = resolve_url("https://www.reddit.com/r/python")
    assert bare is not None and bare.kind == "subreddit" and bare.sort is None
    sorted_ = resolve_url("https://www.reddit.com/r/python/top")
    assert sorted_ is not None and sorted_.sort == "top"


def test_resolve_user_tabs():
    overview = resolve_url("https://www.reddit.com/user/spez")
    assert overview is not None and overview.kind == "user" and overview.content is None
    comments = resolve_url("https://www.reddit.com/u/spez/comments")
    assert comments is not None and comments.content == "comments"


def test_resolve_search_global_and_in_sub():
    global_ = resolve_url("https://www.reddit.com/search/?q=hello")
    assert global_ is not None and global_.kind == "search" and global_.value == "hello"
    in_sub = resolve_url("https://www.reddit.com/r/python/search/?q=async")
    assert in_sub is not None and in_sub.subreddit == "python"


def test_resolve_rejects_non_reddit_host():
    assert resolve_url("https://example.com/r/python") is None
    assert resolve_url("https://notreddit.com/user/x") is None
