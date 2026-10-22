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
