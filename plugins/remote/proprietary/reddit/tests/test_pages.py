"""The Reddit tool reading Reddit's logged-out HTML pages.

Reddit is faked at the page seam, `fetch.fetch_page`, with fixtures cut to the
shape Reddit serves; the host, the tool, the page reading and the scraper are real.
"""

from pathlib import Path
from typing import Any

import pytest

from host.tests.mcp_calls import call
from proprietary.reddit import fetch
from proprietary.reddit.tests.on_the_host import LICENSE, no_proxy_sessions

_FIXTURES = Path(__file__).parent / "fixtures/pages"


def fixture(name: str) -> str:
    return (_FIXTURES / name).read_text()


@pytest.fixture
def pages(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Reddit serving ``served[path]``; every page asked for is kept in ``asked``."""
    served: dict[str, str] = {}
    asked: list[tuple[str, dict[str, Any]]] = []

    async def fetch_page(
        path: str,
        params: dict[str, Any] | None = None,
        *,
        form: dict[str, str] | None = None,
    ) -> Any:
        asked.append((path, {**(params or {}), **({"form": form} if form else {})}))
        return served.get(path)

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(fetch, "fetch_page", fetch_page)
    return {"served": served, "asked": asked}


async def test_a_subreddit_listing_is_read_from_its_page(
    reddit: str, pages: dict[str, Any]
) -> None:
    pages["served"]["svc/shreddit/community-more-posts/new/"] = fixture(
        "community_new.html"
    )

    result = await call(
        reddit,
        "scrape",
        {
            "community": "python",
            "skip_comments": True,
            "include_nsfw": True,
            "max_items": 2,
        },
        LICENSE,
    )

    assert not result.is_error, result.content[0].text
    first, second = result.structured_content["items"]
    assert {
        key: first[key]
        for key in (
            "dataType",
            "id",
            "parsedId",
            "title",
            "username",
            "userId",
            "url",
            "body",
            "communityName",
            "parsedCommunityName",
            "upVotes",
            "upVoteRatio",
            "numberOfComments",
            "flair",
            "over18",
            "createdAt",
        )
    } == {
        "dataType": "post",
        "id": "t3_1xcebo6",
        "parsedId": "1xcebo6",
        "title": "A cheat sheet",
        "username": "ada",
        "userId": "t2_ada",
        "url": "https://www.reddit.com/r/Python/comments/1xcebo6/a_cheat_sheet/",
        "body": "Nine topics.",
        "communityName": "r/Python",
        "parsedCommunityName": "Python",
        "upVotes": 12,
        "upVoteRatio": 0.9,
        "numberOfComments": 3,
        "flair": "Tutorial",
        "over18": False,
        "createdAt": "2026-10-22T09:56:06.051Z",
    }
    assert (second["externalUrl"], second["over18"]) == (
        "https://github.com/fastapi/fastapi/releases",
        True,
    )
    assert ("svc/shreddit/community-more-posts/new/", {"name": "python"}) in pages[
        "asked"
    ]


async def test_a_post_is_read_with_its_comment_tree_from_its_page(
    reddit: str, pages: dict[str, Any]
) -> None:
    """The tree streams in after ``</html>``; a related post's body is not this post's."""
    pages["served"]["comments/1xbnrhi/"] = fixture("post_page.html")

    result = await call(
        reddit,
        "scrape",
        {"urls": ["https://www.reddit.com/r/Python/comments/1xbnrhi/litellm/"]},
        LICENSE,
    )

    assert not result.is_error, result.content[0].text
    post, *comments = result.structured_content["items"]
    assert (post["title"], post["body"], post["numberOfComments"]) == (
        "litellm is compromised",
        "The payload runs on every python start.\n\nRotate your keys.",
        3,
    )
    assert [
        (
            c["id"],
            c["username"],
            c["body"],
            c["upVotes"],
            c["depth"],
            c["parentId"],
            c["postId"],
            c["numberOfReplies"],
            c["communityName"],
        )
        for c in comments
    ] == [
        (
            "t1_aaa",
            "mix",
            "litellm again.",
            159,
            0,
            "t3_1xbnrhi",
            "1xbnrhi",
            0,
            "r/Python",
        ),
        (
            "t1_bbb",
            "boss",
            "Pin your versions.",
            148,
            0,
            "t3_1xbnrhi",
            "1xbnrhi",
            1,
            "r/Python",
        ),
        (
            "t1_ccc",
            "joe",
            "And check hashes.",
            37,
            1,
            "t1_bbb",
            "1xbnrhi",
            0,
            "r/Python",
        ),
    ]
    assert (
        comments[0]["url"]
        == "https://www.reddit.com/r/Python/comments/1xbnrhi/comment/aaa/"
    )
    assert comments[0]["createdAt"] == "2026-10-21T14:01:11.424Z"


async def test_a_subreddit_s_details_come_from_its_top_post_s_page(
    reddit: str, pages: dict[str, Any]
) -> None:
    """Its own pages can serve a JavaScript check; a post page carries its header."""
    pages["served"]["svc/shreddit/community-more-posts/hot/"] = fixture(
        "community_new.html"
    )
    pages["served"]["svc/shreddit/community-more-posts/new/"] = fixture(
        "community_new.html"
    )
    pages["served"]["comments/1xcebo6/"] = fixture("post_page.html")

    result = await call(
        reddit,
        "scrape",
        {"community": "python", "skip_comments": True, "max_items": 1},
        LICENSE,
    )

    assert not result.is_error, result.content[0].text
    (community,) = result.structured_content["items"]
    assert {
        key: community[key]
        for key in (
            "dataType",
            "id",
            "parsedId",
            "url",
            "title",
            "body",
            "communityName",
            "parsedCommunityName",
            "numberOfMembers",
            "over18",
        )
    } == {
        "dataType": "community",
        "id": "t5_2qh0y",
        "parsedId": "2qh0y",
        "url": "https://www.reddit.com/r/Python/",
        "title": "Python",
        "body": "The largest Python community for Reddit!",
        "communityName": "r/Python",
        "parsedCommunityName": "Python",
        "numberOfMembers": 1518857,
        "over18": False,
    }


async def test_search_results_are_read_from_the_search_page(
    reddit: str, pages: dict[str, Any]
) -> None:
    pages["served"]["svc/shreddit/search/"] = fixture("search.html")

    result = await call(
        reddit,
        "scrape",
        {
            "search_queries": ["asyncio"],
            "sort": "top",
            "time_filter": "year",
            "include_nsfw": True,
            "skip_comments": True,
            "max_items": 2,
        },
        LICENSE,
    )

    assert not result.is_error, result.content[0].text
    assert [
        (
            item["id"],
            item["title"],
            item["username"],
            item["userId"],
            item["communityName"],
            item["url"],
            item["upVotes"],
            item["numberOfComments"],
            item["over18"],
            item["createdAt"],
        )
        for item in result.structured_content["items"]
    ] == [
        (
            "t3_1w68fip",
            "Graceful shutdown in asyncio?",
            "breaker",
            "t2_ebt",
            "r/learnpython",
            "https://www.reddit.com/r/learnpython/comments/1w68fip/graceful_shutdown_in_asyncio/",
            2,
            5,
            False,
            "2026-09-03T14:07:02.567Z",
        ),
        (
            "t3_1u9fa2w",
            "asyncio in production",
            "zed",
            "t2_zed",
            "r/Python",
            "https://www.reddit.com/r/Python/comments/1u9fa2w/asyncio_in_production/",
            1200,
            88,
            True,
            "2026-08-01T08:00:00.000Z",
        ),
    ]
    assert pages["asked"][0] == (
        "svc/shreddit/search/",
        {"q": "asyncio", "type": "posts", "sort": "top", "t": "year"},
    )


async def test_a_search_in_one_subreddit_reads_that_subreddit_s_search_page_onward(
    reddit: str, pages: dict[str, Any]
) -> None:
    # Its next page is linked under its own route.
    pages["served"]["svc/shreddit/r/python/search/"] = fixture("search.html").replace(
        "/svc/shreddit/search/", "/svc/shreddit/r/python/search/"
    )

    result = await call(
        reddit,
        "scrape",
        {
            "search_queries": ["asyncio"],
            "community": "python",
            "include_nsfw": True,
            "skip_comments": True,
            "max_items": 3,
        },
        LICENSE,
    )

    assert not result.is_error, result.content[0].text
    first, second = pages["asked"][:2]
    assert first[0] == second[0] == "svc/shreddit/r/python/search/"
    assert second[1]["cursor"] == "eyJjYW5kaWRhdGVzIjoiMiJ9"


async def test_a_user_s_overview_mixes_their_posts_and_comments(
    reddit: str, pages: dict[str, Any]
) -> None:
    pages["served"]["svc/shreddit/profiles/profile_overview-more-posts/new/"] = fixture(
        "user_overview.html"
    )

    result = await call(
        reddit,
        "scrape",
        {"urls": ["https://www.reddit.com/user/spez/"], "max_items": 4},
        LICENSE,
    )

    assert not result.is_error, result.content[0].text
    post, comment, on_own_post, _ = result.structured_content["items"]
    assert (post["dataType"], post["title"], post["upVotes"]) == (
        "post",
        "Modernizing infrastructure",
        357,
    )
    assert {
        key: comment[key]
        for key in (
            "dataType",
            "id",
            "username",
            "body",
            "upVotes",
            "url",
            "postId",
            "communityName",
            "createdAt",
        )
    } == {
        "dataType": "comment",
        "id": "t1_p1wosm9",
        "username": "spez",
        "body": "That was the thinking.",
        "upVotes": 16,
        "url": "https://www.reddit.com/r/Python/comments/1xbnrhi/comment/p1wosm9/",
        "postId": "1xbnrhi",
        "communityName": "r/Python",
        "createdAt": "2026-08-05T18:31:50.140Z",
    }
    # A comment on their own profile's post is in their profile's subreddit.
    assert (on_own_post["communityName"], on_own_post["postId"]) == (
        "u/spez",
        "1vgbkge",
    )
    route = "svc/shreddit/profiles/profile_overview-more-posts/new/"
    assert pages["asked"][:2] == [
        (route, {"name": "spez"}),
        (route, {"name": "spez", "after": "dDFfb3BtYjc2dQ=="}),
    ]


async def test_a_user_s_comments_tab_reads_their_comments_page(
    reddit: str, pages: dict[str, Any]
) -> None:
    route = "svc/shreddit/profiles/profile_comments-more-posts/new/"
    pages["served"][route] = fixture("user_overview.html")

    result = await call(
        reddit,
        "scrape",
        {"urls": ["https://www.reddit.com/user/spez/comments/"], "max_items": 1},
        LICENSE,
    )

    assert not result.is_error, result.content[0].text
    assert [item["id"] for item in result.structured_content["items"]] == ["t1_p1wosm9"]
    assert pages["asked"][0] == (route, {"name": "spez"})


async def test_a_user_s_posts_page_on_from_its_last_post_s_cursor(
    reddit: str, pages: dict[str, Any]
) -> None:
    """That feed links no next page; its posts carry the cursor instead."""
    route = "svc/shreddit/profiles/profile_posts-more-posts/new/"
    page = fixture("user_overview.html")
    pages["served"][route] = page[: page.index("<faceplate-partial")]

    await call(
        reddit,
        "scrape",
        {"urls": ["https://www.reddit.com/user/spez/submitted/"], "max_items": 5},
        LICENSE,
    )

    assert pages["asked"][1] == (route, {"name": "spez", "after": "dDNfMXZnYmtnZQ"})


async def test_a_post_s_later_comments_load_until_enough_are_read(
    reddit: str, pages: dict[str, Any]
) -> None:
    """Its page holds the first batch; the rest load from a POST with its cursor."""
    pages["served"]["comments/1xbnrhi/"] = fixture("post_page.html")
    more = "svc/shreddit/more-comments/Python/t3_1xbnrhi"
    pages["served"][more] = fixture("more_comments.html")

    result = await call(
        reddit,
        "scrape",
        {
            "urls": ["https://www.reddit.com/r/Python/comments/1xbnrhi/litellm/"],
            "max_comments": 5,
        },
        LICENSE,
    )

    assert not result.is_error, result.content[0].text
    _, *comments = result.structured_content["items"]
    assert [c["id"] for c in comments] == [
        "t1_aaa",
        "t1_bbb",
        "t1_ccc",
        "t1_ddd",
        "t1_eee",
    ]
    (loaded,) = [params for path, params in pages["asked"] if path == more]
    assert loaded == {
        "top-level": "1",
        "comments-remaining": "2",
        "commentPositionOffset": "3",
        "form": {"cursor": "Y29tbWVudHRyZWU6MQ"},
    }


async def test_a_post_with_enough_comments_on_its_page_loads_no_more(
    reddit: str, pages: dict[str, Any]
) -> None:
    pages["served"]["comments/1xbnrhi/"] = fixture("post_page.html")

    await call(
        reddit,
        "scrape",
        {
            "urls": ["https://www.reddit.com/r/Python/comments/1xbnrhi/litellm/"],
            "max_comments": 3,
        },
        LICENSE,
    )

    assert [path for path, _ in pages["asked"]] == ["comments/1xbnrhi/"]
