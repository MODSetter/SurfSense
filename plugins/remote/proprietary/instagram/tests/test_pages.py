"""The Instagram tools reading a profile from the pages Instagram serves logged out.

Instagram is faked at the scraper's page seam, `fetch_html`, with fixtures cut to
the shape Instagram serves; the host, the tools, the page reading and parsing are real.
"""

import asyncio
import contextvars
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from host.tests.mcp_calls import call
from proprietary.instagram import scraper
from proprietary.instagram.fetch import InstagramAccessBlockedError
from proprietary.instagram.tests.on_the_host import LICENSE, no_proxy_sessions

_FIXTURES = Path(__file__).parent / "fixtures/pages"


def fixture(name: str) -> str:
    return (_FIXTURES / name).read_text()


@pytest.fixture
def pages(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """natgeo's profile, embed, reels tab and post pages; keeps each path asked for."""
    served = {
        "natgeo/": fixture("profile_page.html"),
        "natgeo/embed/": fixture("profile_embed.html"),
        "natgeo/reels/": fixture("reels_page.html"),
    }
    for code in ("PINNED0001", "OLDER00004", "REEL000001", "REEL000002"):
        served[f"p/{code}/"] = fixture(f"post_{code}.html")
    asked: list[str] = []

    async def fetch_html(path: str, params: dict | None = None) -> str | None:
        asked.append(path)
        return served.get(path)

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "fetch_html", fetch_html)
    return asked


async def test_a_profile_s_details_come_from_its_page_and_its_embed(
    instagram: str, pages: list[str]
) -> None:
    """``web_profile_info`` asks for a login; the two pages a visitor sees do not."""
    result = await call(instagram, "details", {"urls": ["natgeo"]}, LICENSE)

    assert not result.is_error, result.content[0].text
    (profile,) = result.structured_content["items"]
    assert {
        key: profile[key]
        for key in (
            "id",
            "username",
            "fullName",
            "biography",
            "externalUrl",
            "followersCount",
            "followsCount",
            "postsCount",
            "verified",
            "private",
        )
    } == {
        "id": "787132",
        "username": "natgeo",
        "fullName": "National Geographic",
        "biography": "Step into wonder.",
        "externalUrl": "http://visitstore.bio/natgeo",
        "followersCount": 268309105,
        "followsCount": 195,
        "postsCount": 32104,
        "verified": True,
        "private": False,
    }
    assert [(p["shortCode"], p["likesCount"]) for p in profile["latestPosts"]] == [
        ("NEWEST0001", 22137),
        ("NEWER00002", 9000),
        ("NEWER00003", 5000),
    ]


async def test_a_profile_s_posts_read_in_full_with_its_pinned_post_first(
    instagram: str, pages: list[str]
) -> None:
    """The embed holds the newest in full; a post it leaves out is read from its page."""
    result = await call(
        instagram, "scrape", {"urls": ["natgeo"], "max_per_target": 5}, LICENSE
    )

    assert not result.is_error, result.content[0].text
    assert [
        (
            p["shortCode"],
            p["isPinned"],
            p["likesCount"],
            p["commentsCount"],
            p["timestamp"],
        )
        for p in result.structured_content["items"]
    ] == [
        ("PINNED0001", True, 100000, 900, "2026-05-28T20:26:40.000Z"),
        ("NEWEST0001", False, 22137, 108, "2026-10-21T22:08:24.000Z"),
        ("NEWER00002", False, 9000, 40, "2026-10-21T16:26:40.000Z"),
        ("NEWER00003", False, 5000, 20, "2026-10-20T12:40:00.000Z"),
        ("OLDER00004", False, 3000, 12, "2026-10-19T08:53:20.000Z"),
    ]
    assert pages.count("p/NEWEST0001/") == 0


async def test_skipping_pinned_posts_leaves_the_post_the_embed_left_out(
    instagram: str, pages: list[str]
) -> None:
    result = await call(
        instagram,
        "scrape",
        {"urls": ["natgeo"], "skip_pinned_posts": True, "max_per_target": 2},
        LICENSE,
    )

    assert [p["shortCode"] for p in result.structured_content["items"]] == [
        "NEWEST0001",
        "NEWER00002",
    ]
    assert "p/PINNED0001/" not in pages


async def test_a_profile_s_reels_come_from_its_reels_tab(
    instagram: str, pages: list[str]
) -> None:
    result = await call(
        instagram, "scrape", {"urls": ["natgeo"], "result_type": "reels"}, LICENSE
    )

    assert not result.is_error, result.content[0].text
    assert [
        (r["shortCode"], r["isPinned"], r["type"], r["videoViewCount"], r["likesCount"])
        for r in result.structured_content["items"]
    ] == [
        ("REEL000002", True, "Video", 600000, 20000),
        ("REEL000001", False, "Video", 1200000, 40000),
    ]


async def test_a_post_from_the_embed_takes_what_the_embed_lacks_from_the_grid(
    instagram: str, pages: list[str]
) -> None:
    """The embed has no product type, alt text or owner's name; the pages read do."""
    result = await call(
        instagram,
        "scrape",
        {"urls": ["natgeo"], "skip_pinned_posts": True, "max_per_target": 1},
        LICENSE,
    )

    (newest,) = result.structured_content["items"]
    assert (newest["shortCode"], newest["productType"], newest["alt"]) == (
        "NEWEST0001",
        "clips",
        "Wolves running through snow",
    )
    assert newest["ownerFullName"] == "National Geographic"


async def test_a_reels_feed_does_not_ask_for_the_embed(
    instagram: str, pages: list[str]
) -> None:
    """Each reel is read from its own page, for its video; the embed would go unused."""
    await call(
        instagram, "scrape", {"urls": ["natgeo"], "result_type": "reels"}, LICENSE
    )

    assert "natgeo/embed/" not in pages


@pytest.fixture
def lanes(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    """natgeo's pages, each fetch kept with the session it was read on."""
    served = {
        "natgeo/": fixture("profile_page.html"),
        "natgeo/embed/": fixture("profile_embed.html"),
        "natgeo/reels/": fixture("reels_page.html"),
    }
    for code in ("PINNED0001", "OLDER00004", "REEL000001", "REEL000002"):
        served[f"p/{code}/"] = fixture(f"post_{code}.html")
    seen: dict[str, list] = {"opened": [], "fetched": []}
    held: list[object] = []

    class Holder:
        async def close(self) -> None:
            pass

    async def open_holder() -> Holder:
        seen["opened"].append(Holder())
        return seen["opened"][-1]

    @asynccontextmanager
    async def bind(holder: Holder) -> AsyncIterator[Holder]:
        token = _bound.set(holder)
        held.append(holder)
        try:
            yield holder
        finally:
            _bound.reset(token)

    async def fetch_html(path: str, params: dict | None = None) -> str | None:
        seen["fetched"].append((path, _bound.get()))
        await asyncio.sleep(0)
        return served.get(path)

    monkeypatch.setattr(scraper, "open_proxy_holder", open_holder)
    monkeypatch.setattr(scraper, "bind_proxy_holder", bind)
    monkeypatch.setattr(scraper, "fetch_html", fetch_html)
    return seen


_bound: contextvars.ContextVar[object | None] = contextvars.ContextVar(
    "bound", default=None
)


async def test_posts_the_embed_lacks_are_read_on_separate_exits_at_once(
    instagram: str, lanes: dict[str, list]
) -> None:
    """One exit read them one after another: 6 pages took 16.8s, on 3 exits 7.8s."""
    result = await call(
        instagram, "scrape", {"urls": ["natgeo"], "max_per_target": 5}, LICENSE
    )

    assert [p["shortCode"] for p in result.structured_content["items"]] == [
        "PINNED0001",
        "NEWEST0001",
        "NEWER00002",
        "NEWER00003",
        "OLDER00004",
    ]
    exits = {holder for path, holder in lanes["fetched"] if path.startswith("p/")}
    assert len(exits) == 2


async def test_a_feed_reads_no_post_page_past_what_it_needs(
    instagram: str, lanes: dict[str, list]
) -> None:
    await call(
        instagram,
        "scrape",
        {"urls": ["natgeo"], "skip_pinned_posts": True, "max_per_target": 3},
        LICENSE,
    )

    assert not [path for path, _ in lanes["fetched"] if path.startswith("p/")]


async def test_a_blocked_post_page_is_the_refusal_and_stops_the_other_exits(
    instagram: str, lanes: dict[str, list], monkeypatch: pytest.MonkeyPatch
) -> None:
    fetched = scraper.fetch_html
    after: list[str] = []

    async def blocked(path: str, params: dict | None = None) -> str | None:
        if path == "p/PINNED0001/":
            raise InstagramAccessBlockedError("Instagram refused p/PINNED0001/")
        if path == "p/OLDER00004/":
            await asyncio.sleep(0.2)  # still reading when the other exit fails
            after.append(path)
        return await fetched(path, params)

    monkeypatch.setattr(scraper, "fetch_html", blocked)

    result = await call(
        instagram, "scrape", {"urls": ["natgeo"], "max_per_target": 5}, LICENSE
    )

    assert result.is_error
    assert "Instagram refused p/PINNED0001/" in result.content[0].text
    assert after == []
