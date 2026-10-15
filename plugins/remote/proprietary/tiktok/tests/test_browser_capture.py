"""The browser seam's page logic over a fake page and a fake clock (no browser).

Covers the event-driven waits (stop on the capture, cap when nothing comes),
the comment panel's JS click, user search's in-page retry, bounced exits, the
shared-pool page arguments (media blocking, fail-fast timeout) and the hedged
rotation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest

from proprietary.tiktok.extraction import (
    comments_from_response,
    items_from_response,
    users_from_response,
)
from proprietary.tiktok.session import listing

_UNSET = object()


class _Response:
    def __init__(self, url: str, body: Any):
        self.url = url
        self._body = body

    async def json(self) -> Any:
        if self._body is None:
            raise ValueError("empty body")
        return self._body


class _Page:
    """A page whose matching XHRs land at scheduled fake-clock times."""

    def __init__(
        self,
        *,
        url: str = "about:blank",
        goto_url: str | None = None,
        selectors: tuple[str, ...] = (),
        on_nudge: Callable[[_Page], None] | None = None,
        on_click: Callable[[_Page], None] | None = None,
        on_retry: Callable[[_Page], None] | None = None,
        on_reload: Callable[[_Page], None] | None = None,
        goto_error: Exception | None = None,
    ):
        self.url = url
        self.goto_url = goto_url
        self.selectors = selectors
        self.on_nudge = on_nudge
        self.on_click = on_click
        self.on_retry = on_retry
        self.on_reload = on_reload
        self.goto_error = goto_error
        self.clock_ms = 0
        self.listeners: list[Callable[[Any], Any]] = []
        self.pending: list[tuple[int, _Response]] = []
        self.calls: list[str] = []

    # Scheduling ---------------------------------------------------------
    def respond(self, after_ms: int, url: str, body: Any) -> None:
        self.pending.append((self.clock_ms + after_ms, _Response(url, body)))

    async def _fire_due(self) -> None:
        due = [p for p in self.pending if p[0] <= self.clock_ms]
        self.pending = [p for p in self.pending if p[0] > self.clock_ms]
        for _, response in sorted(due, key=lambda p: p[0]):
            for listener in self.listeners:
                await listener(response)

    # Playwright surface the seam uses -----------------------------------
    def on(self, _event: str, listener: Callable[[Any], Any]) -> None:
        self.listeners.append(listener)

    async def wait_for_timeout(self, ms: int) -> None:
        self.clock_ms += ms
        await self._fire_due()

    async def goto(self, url: str, **_kwargs: Any) -> None:
        self.calls.append(f"goto {url}")
        if self.goto_error is not None:
            raise self.goto_error
        self.url = self.goto_url or url

    async def wait_for_load_state(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def reload(self, wait_until: str | None = None) -> None:
        self.calls.append("reload")
        if self.on_reload:
            self.on_reload(self)

    async def evaluate(self, script: str) -> Any:
        if "modal-close-inner-button" in script:
            return True
        if "search-error-title" in script:
            self.calls.append("retry-click")
            if self.on_retry:
                self.on_retry(self)
            return True
        if "scrollTo" in script or "scrollIntoView" in script:
            self.calls.append("nudge")
            if self.on_nudge:
                self.on_nudge(self)
            return True
        return None

    async def wait_for_selector(self, selector: str, **kwargs: Any) -> None:
        self.calls.append(f"wait {selector}")
        if selector not in self.selectors:
            self.clock_ms += kwargs.get("timeout") or 0
            raise TimeoutError(selector)

    async def eval_on_selector(self, selector: str, script: str) -> None:
        self.calls.append(f"js-click {selector}")
        if self.on_click:
            self.on_click(self)

    async def click(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("page.click times out live; the seam must click by JS")


_ITEMS = "https://www.tiktok.com/api/post/item_list/?x=1"
_USERS = "https://www.tiktok.com/api/search/user/full/?q=nike"
_COMMENTS = "https://www.tiktok.com/api/comment/list/?aweme_id=1"


def _feed(n: int, start: int = 0) -> dict:
    return {"itemList": [{"id": str(i)} for i in range(start, start + n)]}


async def _run(page: _Page, interact, markers, extract, target: int, url: str):
    capture = listing._Capture()
    await listing._drive(
        page, capture, url, target, markers, extract, interact, kind="test"
    )
    return capture


async def _listing(page: _Page, target: int):
    return await _run(
        page,
        listing._scroll_page,
        listing._ITEM_LIST_MARKERS,
        items_from_response,
        target,
        "https://www.tiktok.com/@tiktok",
    )


async def test_listing_goes_straight_to_the_target():
    page = _Page()
    page.respond(700, _ITEMS, _feed(5))

    await _listing(page, 3)

    # No robots.txt primer and no homepage warm-up: one goto, to the target.
    assert [c for c in page.calls if c.startswith("goto")] == [
        "goto https://www.tiktok.com/@tiktok"
    ]


async def test_listing_stops_as_soon_as_page_one_is_enough():
    page = _Page()
    page.respond(700, _ITEMS, _feed(5))

    capture = await _listing(page, 3)

    assert len(capture.items) == 5
    assert "nudge" not in page.calls  # no scroll once enough is in
    assert page.clock_ms <= 800  # the old fixed settle alone was 1500 ms


async def test_listing_pages_on_scroll_until_the_feed_dries_up():
    pages = iter([_feed(2, 2), _feed(2, 4), _feed(2, 6)])

    def nudge(page: _Page) -> None:
        body = next(pages, _UNSET)
        if body is not _UNSET:
            page.respond(300, _ITEMS, body)

    page = _Page(on_nudge=nudge)
    page.respond(500, _ITEMS, _feed(2))

    capture = await _listing(page, 10)

    assert [i["id"] for i in capture.items] == [str(i) for i in range(8)]
    # three answered rounds, then one capped round that brings nothing
    assert page.clock_ms <= 500 + 3 * 400 + listing._ROUND_RESPONSE_MS + 100


async def test_listing_caps_its_waits_when_nothing_arrives():
    page = _Page()

    capture = await _listing(page, 3)

    assert capture.items == []
    assert page.clock_ms == listing._FIRST_RESPONSE_MS + listing._ROUND_RESPONSE_MS


async def test_a_cold_empty_first_item_list_is_retriggered_by_one_scroll():
    def nudge(page: _Page) -> None:
        if page.calls.count("nudge") == 1:
            page.respond(400, _ITEMS, _feed(16))

    page = _Page(on_nudge=nudge)
    page.respond(600, _ITEMS, None)  # cold context: empty first body

    capture = await _listing(page, 3)

    assert capture.empty == 1
    assert len(capture.items) == 16
    assert page.calls.count("nudge") == 1
    assert "reload" not in page.calls


async def test_an_empty_feed_that_will_not_scroll_is_reloaded_once():
    def reloaded(page: _Page) -> None:
        page.respond(900, _ITEMS, _feed(16))

    page = _Page(on_reload=reloaded)
    page.respond(600, _ITEMS, None)

    capture = await _listing(page, 3)

    assert len(capture.items) == 16
    assert page.calls.count("reload") == 1


async def test_an_empty_feed_is_reloaded_at_most_once():
    def reloaded(page: _Page) -> None:
        page.respond(900, _ITEMS, None)

    page = _Page(on_reload=reloaded)
    page.respond(600, _ITEMS, None)

    capture = await _listing(page, 3)

    assert capture.items == []
    assert page.calls.count("reload") == 1


async def test_a_feed_that_never_answered_is_not_reloaded():
    page = _Page()

    await _listing(page, 3)

    assert "reload" not in page.calls


@pytest.mark.parametrize(
    ("bounce", "reason"),
    [
        ("https://www.tiktok.com/hk/notfound", "geo_block"),
        ("https://www.tiktok.com/login?redirect_url=x", "login"),
    ],
)
async def test_a_bounced_exit_ends_the_attempt_at_once(bounce: str, reason: str):
    interacted: list[bool] = []

    async def interact(*_args: Any) -> None:
        interacted.append(True)

    page = _Page(goto_url=bounce)
    capture = await _run(
        page, interact, listing._ITEM_LIST_MARKERS, items_from_response, 3, "u"
    )

    assert capture.exit_reason == reason
    assert interacted == []


async def test_a_dead_exit_is_a_page_error_logged_with_its_stage(caplog):
    page = _Page(goto_error=TimeoutError("commit timed out"))

    with caplog.at_level(logging.WARNING, logger=listing.logger.name):
        capture = await _listing(page, 3)

    assert capture.exit_reason == "page_error"
    assert "test goto failed (TimeoutError)" in caplog.text


def test_a_login_handle_is_not_a_login_wall():
    assert listing._bad_exit_reason("https://www.tiktok.com/@login") == ""
    assert listing._bad_exit_reason("https://www.tiktok.com/explore") == ""


async def _comments(page: _Page, target: int):
    return await _run(
        page,
        listing._scroll_comments,
        listing._COMMENT_MARKERS,
        comments_from_response,
        target,
        "https://www.tiktok.com/@a/video/1",
    )


async def test_comments_open_by_js_click_and_stop_on_the_first_page():
    def clicked(page: _Page) -> None:
        page.respond(400, _COMMENTS, {"comments": [{"cid": str(i)} for i in range(20)]})

    page = _Page(selectors=(listing._COMMENT_ICON_SELECTOR,), on_click=clicked)

    capture = await _comments(page, 5)

    assert len(capture.items) == 20
    assert f"js-click {listing._COMMENT_ICON_SELECTOR}" in page.calls
    assert page.clock_ms <= 500  # the old fixed first-page wait was 3500 ms


async def test_an_early_click_that_fires_nothing_is_repeated():
    def clicked(page: _Page) -> None:
        # The first click lands before the SPA wires the icon up.
        if page.calls.count(f"js-click {listing._COMMENT_ICON_SELECTOR}") == 2:
            page.respond(400, _COMMENTS, {"comments": [{"cid": "1"}]})

    page = _Page(selectors=(listing._COMMENT_ICON_SELECTOR,), on_click=clicked)

    capture = await _comments(page, 1)

    assert len(capture.items) == 1
    assert page.calls.count(f"js-click {listing._COMMENT_ICON_SELECTOR}") == 2


async def test_comment_clicks_are_capped():
    page = _Page(selectors=(listing._COMMENT_ICON_SELECTOR,))

    capture = await _comments(page, 5)

    assert capture.items == []
    clicks = page.calls.count(f"js-click {listing._COMMENT_ICON_SELECTOR}")
    assert clicks == listing._COMMENT_CLICKS
    assert "nudge" not in page.calls  # no panel, so no paging
    assert page.clock_ms == listing._COMMENT_CLICKS * listing._COMMENT_RECLICK_MS


async def test_a_missing_comment_icon_is_logged_with_its_stage(caplog):
    page = _Page()

    with caplog.at_level(logging.WARNING, logger=listing.logger.name):
        capture = await _comments(page, 5)

    assert capture.items == []
    assert "test interact failed (TimeoutError)" in caplog.text


async def _users(page: _Page, target: int):
    return await _run(
        page,
        listing._search_users,
        listing._USER_SEARCH_MARKERS,
        users_from_response,
        target,
        "https://www.tiktok.com/search/user?q=nike",
    )


def _user_list(n: int) -> dict:
    return {"user_list": [{"user_info": {"uid": str(i)}} for i in range(n)]}


async def test_user_search_recovers_an_empty_body_in_the_page():
    def retried(page: _Page) -> None:
        page.respond(700, _USERS, _user_list(10))

    page = _Page(selectors=(listing._SEARCH_ERROR_TITLE,), on_retry=retried)
    page.respond(500, _USERS, None)

    capture = await _users(page, 3)

    assert len(capture.items) == 10
    assert page.calls.count("retry-click") == 1


async def test_a_real_no_match_never_clicks_retry():
    page = _Page(selectors=(listing._SEARCH_ERROR_TITLE,))
    page.respond(500, _USERS, {"user_list": []})

    capture = await _users(page, 3)

    assert capture.items == []
    assert "retry-click" not in page.calls
    assert page.clock_ms <= 600


async def test_user_search_retries_at_most_twice_then_rotates():
    def retried(page: _Page) -> None:
        page.respond(300, _USERS, None)

    page = _Page(selectors=(listing._SEARCH_ERROR_TITLE,), on_retry=retried)
    page.respond(500, _USERS, None)

    capture = await _users(page, 3)

    assert capture.items == []
    assert page.calls.count("retry-click") == listing._SEARCH_MAX_RETRIES


class _Pooled:
    def __init__(self, page: _Page) -> None:
        self.page = page
        self.burned: str | None = None

    def burn(self, reason: str) -> None:
        self.burned = reason


def _fake_pool(monkeypatch, page_for: Callable[[str | None], _Page]) -> list[dict]:
    """Serve ``browser_pool.page`` from fakes; returns each page() call's arguments."""
    lent: list[dict] = []

    @asynccontextmanager
    async def page(plugin, profile, **kwargs):
        pooled = _Pooled(page_for(kwargs.get("proxy")))
        lent.append({"plugin": plugin, "profile": profile, "pooled": pooled, **kwargs})
        yield pooled

    async def run(fn):
        return await fn()

    monkeypatch.setattr(listing.browser_pool, "page", page)
    monkeypatch.setattr(listing.browser_pool, "run", run)
    monkeypatch.setattr(listing, "get_geo_proxy_url", lambda country: country)
    return lent


async def _draw(**overrides: Any) -> tuple[list, listing._Capture]:
    capture = listing._Capture()
    kwargs = {"country": "us", "capture": capture, "kind": "hashtag", **overrides}
    items = await listing._draw(
        "https://www.tiktok.com/tag/cooking",
        3,
        listing._ITEM_LIST_MARKERS,
        items_from_response,
        listing._scroll_page,
        **kwargs,
    )
    return items, capture


async def test_a_draw_lends_a_fresh_pooled_page_that_blocks_media(monkeypatch):
    def fed(_proxy):
        page = _Page()
        page.respond(300, _ITEMS, _feed(3))
        return page

    lent = _fake_pool(monkeypatch, fed)

    items, _ = await _draw()

    assert len(items) == 3
    (call,) = lent
    assert call["plugin"] == "tiktok"
    assert call["proxy"] == "us"
    assert "kept" not in call  # a fresh context per draw
    assert call["disable_resources"] == {"image", "media", "font"}  # stylesheets stay
    assert "/video/tos/" in call["block_url_patterns"]
    assert call["timeout_ms"] == 12000
    assert call["profile"].headless is True


async def test_media_blocking_has_a_kill_switch(monkeypatch):
    lent = _fake_pool(monkeypatch, lambda _proxy: _Page())
    monkeypatch.setattr(listing, "_BLOCK_MEDIA", False)

    await _draw()

    assert lent[0]["disable_resources"] is False
    assert lent[0]["block_url_patterns"] == ()


async def test_a_bounced_exit_burns_its_context(monkeypatch):
    lent = _fake_pool(
        monkeypatch, lambda _proxy: _Page(goto_url="https://www.tiktok.com/hk/notfound")
    )

    items, capture = await _draw()

    assert items == []
    assert capture.exit_reason == "geo_block"
    assert lent[0]["pooled"].burned == "geo_block"


async def test_a_pool_failure_is_an_empty_draw(monkeypatch, caplog):
    async def run(_fn):
        raise TimeoutError("new_context wedged")

    monkeypatch.setattr(listing.browser_pool, "run", run)

    with caplog.at_level(logging.WARNING, logger=listing.logger.name):
        items, capture = await _draw()

    assert items == []
    assert capture.exit_reason == "page_error"
    assert "hashtag browser attempt failed" in caplog.text


async def test_the_retry_line_names_the_target_kind_and_reason(monkeypatch, caplog):
    draws = iter([([], "geo_block"), ([{"id": "1"}], "")])

    async def draw(*_args: Any, capture, **_kwargs: Any) -> list[dict]:
        items, reason = next(draws)
        capture.exit_reason = reason
        return items

    monkeypatch.setattr(listing, "_draw", draw)
    monkeypatch.setattr(listing, "_LISTING_MAX_ATTEMPTS", 3)

    with caplog.at_level(logging.INFO, logger=listing.logger.name):
        items = await listing.fetch_item_list(
            "https://www.tiktok.com/search?q=pasta", 3
        )

    assert items == [{"id": "1"}]
    assert "empty search for https://www.tiktok.com/search?q=pasta" in caplog.text
    assert "reason=geo_block" in caplog.text
    assert "geo_block exit on country=" in caplog.text
    assert "/api/post/item_list" not in caplog.text


async def test_a_draw_with_no_first_xhr_is_hedged_on_the_next_country(monkeypatch):
    countries: list[str] = []
    cancelled: list[str] = []

    async def draw(*_args: Any, country: str, capture, **_kwargs: Any) -> list[dict]:
        countries.append(country)
        capture.lent_at = time.monotonic()  # the pool lends a page at once
        if len(countries) == 1:
            try:
                await asyncio.sleep(5)  # a slow exit: no XHR yet
            except asyncio.CancelledError:
                cancelled.append(country)
                raise
        return [{"id": country}]

    monkeypatch.setattr(listing, "_draw", draw)
    monkeypatch.setattr(listing, "_HEDGE_AFTER_S", 0.05)
    monkeypatch.setattr(
        listing, "country_for_rotation", lambda n: ("us", "gb", "de")[n % 3]
    )

    items = await asyncio.wait_for(
        listing.fetch_item_list("https://www.tiktok.com/tag/a", 3), timeout=2
    )

    assert items == [{"id": "gb"}]
    assert countries == ["us", "gb"]
    assert cancelled == ["us"]  # the slow attempt's context closes


async def test_a_slow_feed_whose_first_xhr_came_is_not_hedged(monkeypatch):
    countries: list[str] = []

    async def draw(*_args: Any, country: str, capture, **_kwargs: Any) -> list[dict]:
        countries.append(country)
        capture.responses = 1  # page one arrived; paging is just slow
        await asyncio.sleep(0.2)
        return [{"id": country}]

    monkeypatch.setattr(listing, "_draw", draw)
    monkeypatch.setattr(listing, "_HEDGE_AFTER_S", 0.05)

    items = await listing.fetch_item_list("https://www.tiktok.com/tag/a", 3)

    assert len(items) == 1
    assert len(countries) == 1


def test_listing_kind_from_the_url():
    assert listing._listing_kind("https://www.tiktok.com/@tiktok") == "profile"
    assert listing._listing_kind("https://www.tiktok.com/tag/cats") == "hashtag"
    assert listing._listing_kind("https://www.tiktok.com/search?q=a") == "search"


def _queued_pool(monkeypatch, delays: list[float]) -> list[dict]:
    """Like ``_fake_pool``, but each lend first waits its delay (a full pool)."""
    lent: list[dict] = []
    waits = iter(delays)

    @asynccontextmanager
    async def page(plugin, profile, **kwargs):
        await asyncio.sleep(next(waits, 0))
        fed = _Page()
        fed.respond(300, _ITEMS, _feed(3))
        lent.append({"proxy": kwargs.get("proxy"), "page": fed})
        yield _Pooled(fed)

    async def run(fn):
        return await fn()

    monkeypatch.setattr(listing.browser_pool, "page", page)
    monkeypatch.setattr(listing.browser_pool, "run", run)
    monkeypatch.setattr(listing, "get_geo_proxy_url", lambda country: country)
    return lent


async def test_time_queued_for_a_page_does_not_start_a_hedge(monkeypatch):
    # The first draw waits 0.3 s for a page, six hedge periods: not a slow exit.
    lent = _queued_pool(monkeypatch, [0.3])
    monkeypatch.setattr(listing, "_HEDGE_AFTER_S", 0.05)

    items = await asyncio.wait_for(
        listing.fetch_item_list("https://www.tiktok.com/tag/a", 3), timeout=2
    )

    assert len(items) == 3
    assert len(lent) == 1  # no second page was asked for


async def test_a_hedge_lent_its_page_after_page_one_came_never_navigates(
    monkeypatch, caplog
):
    lent = _fake_pool(monkeypatch, lambda _proxy: _Page())

    with caplog.at_level(logging.INFO, logger=listing.logger.name):
        items, capture = await _draw(abandon=lambda: True)

    assert items == []
    assert capture.skipped and capture.done
    assert lent[0]["pooled"].page.calls == []  # no goto
    assert "hashtag hedge skipped: page one came" in caplog.text


async def test_a_skipped_hedge_spends_no_attempt(monkeypatch):
    countries: list[str] = []

    async def draw(
        *_args: Any, country: str, capture, abandon=None, **_kwargs: Any
    ) -> list[dict]:
        countries.append(country)
        capture.lent_at = time.monotonic()
        if abandon is not None:  # the hedge: page one came while it queued
            capture.skipped = True
            return []
        await asyncio.sleep(0.2)
        return [] if len(countries) < 3 else [{"id": country}]

    monkeypatch.setattr(listing, "_draw", draw)
    monkeypatch.setattr(listing, "_HEDGE_AFTER_S", 0.05)
    monkeypatch.setattr(listing, "_LISTING_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(
        listing, "country_for_rotation", lambda n: ("us", "gb", "de")[n % 3]
    )

    items = await listing.fetch_item_list("https://www.tiktok.com/tag/a", 3)

    # us (its hedge on gb skipped), then gb drawn for real on the second round.
    assert countries[:3] == ["us", "gb", "gb"]
    assert items == [{"id": "gb"}]


async def test_zero_hedge_delay_turns_the_hedge_off(monkeypatch):
    countries: list[str] = []

    async def draw(*_args: Any, country: str, capture, **_kwargs: Any) -> list[dict]:
        countries.append(country)
        capture.lent_at = time.monotonic()
        await asyncio.sleep(0.1)
        return [{"id": country}]

    monkeypatch.setattr(listing, "_draw", draw)
    monkeypatch.setattr(listing, "_HEDGE_AFTER_S", 0.0)

    items = await listing.fetch_item_list("https://www.tiktok.com/tag/a", 3)

    assert len(items) == 1
    assert len(countries) == 1


async def test_a_hedge_backs_out_when_page_one_comes_while_it_waits(
    monkeypatch, caplog
):
    countries: list[str] = []

    async def draw(*_args: Any, country: str, capture, **_kwargs: Any) -> list[dict]:
        countries.append(country)
        await asyncio.sleep(0.1)  # still launching a browser
        capture.lent_at = time.monotonic()
        await asyncio.sleep(0.02)
        capture.responses = 1  # page one, before the page was held 0.05 s
        await asyncio.sleep(0.2)
        return [{"id": country}]

    monkeypatch.setattr(listing, "_draw", draw)
    monkeypatch.setattr(listing, "_HEDGE_AFTER_S", 0.05)

    with caplog.at_level(logging.INFO, logger=listing.logger.name):
        items = await listing.fetch_item_list("https://www.tiktok.com/tag/a", 3)

    assert len(items) == 1
    assert len(countries) == 1
    assert "hashtag hedge skipped: page one came" in caplog.text
