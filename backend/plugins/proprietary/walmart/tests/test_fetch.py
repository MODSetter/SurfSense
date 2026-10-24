"""The Walmart fetch policy on the shared transport: blocks, redirects, hedges, budget."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from proprietary.scraping import http, sessions
from proprietary.walmart import fetch
from proprietary.walmart.tests.fake_http import answering, raw

_PRODUCT = (Path(__file__).parent / "fixtures" / "product.html").read_text("utf-8")
_ID_URL = "https://www.walmart.com/ip/212092810"
_SLUG_URL = "https://www.walmart.com/ip/Midea-AC/212092810"


@pytest.mark.parametrize("first_status", [444, 520])
async def test_an_edge_error_is_retried_on_a_fresh_exit(monkeypatch, first_status):
    """A 444 or 520 is not a page: before, a 444 became product_not_found and a
    520 ended review pagination early."""
    statuses = [first_status, 200]
    asked = answering(
        monkeypatch,
        lambda url: raw(url, _PRODUCT if statuses[0] == 200 else "", statuses.pop(0)),
    )

    result = await fetch.fetch_page(_ID_URL)

    assert result is not None and result.status == 200
    assert "__NEXT_DATA__" in result.html
    assert len(asked) == 2


async def test_the_redirect_to_the_slug_page_is_followed_on_the_same_session(
    monkeypatch,
):
    """/ip/{id} redirects to its slug page; the hop is followed by hand, once."""
    exits: list[sessions.Exit] = []
    real_holder = sessions.holder

    def holder(plugin, exit=None, **kw):
        exits.append(exit)
        return real_holder(plugin, exit, **kw)

    monkeypatch.setattr(sessions, "holder", holder)
    asked = answering(
        monkeypatch,
        lambda url: (
            raw(url, status=301, location="/ip/Midea-AC/212092810")
            if url == _ID_URL
            else raw(url, _PRODUCT)
        ),
    )

    result = await fetch.fetch_page(_ID_URL)

    assert result is not None and result.url == _SLUG_URL
    assert asked == [_ID_URL, _SLUG_URL]
    assert len(exits) == 1  # both hops on the one try's session


async def test_a_redirect_chain_past_the_follow_limit_moves_to_a_fresh_exit(
    monkeypatch,
):
    """A try still redirecting after its last hop has no page: before, its empty
    3xx came back as the page, so the product read as not found."""
    redirects = [fetch._MAX_FOLLOWS + 1]

    def respond(url: str) -> http.RawResponse:
        if redirects[0]:
            redirects[0] -= 1
            return raw(url, status=302, location=f"{_SLUG_URL}?hop={redirects[0]}")
        return raw(url, _PRODUCT)

    asked = answering(monkeypatch, respond)

    result = await fetch.fetch_page(_ID_URL)

    assert result is not None and result.status == 200
    assert "__NEXT_DATA__" in result.html
    # The first try's whole chain, then the page on a fresh exit.
    assert len(asked) == fetch._MAX_FOLLOWS + 2
    assert asked[-1] == _ID_URL


async def test_a_redirect_to_blocked_fails_the_try_without_loading_it(monkeypatch):
    blocked_once = [True]

    def respond(url: str) -> http.RawResponse:
        if "/blocked" in url:
            return raw(url, "Robot or human?")
        if blocked_once.pop() if blocked_once else False:
            return raw(url, status=307, location="/blocked?url=L2lwLzIxMjA5MjgxMA==")
        return raw(url, _PRODUCT)

    asked = answering(monkeypatch, respond)

    result = await fetch.fetch_page(_ID_URL)

    assert result is not None and result.status == 200
    assert asked == [_ID_URL, _ID_URL]  # the /blocked page itself is never asked


async def test_a_captcha_page_and_a_px_rejection_are_blocks():
    captcha = raw(_ID_URL, "<html><title>Robot or human?</title></html>")
    rejected = raw(_ID_URL, "", 412)
    to_blocked = raw(_ID_URL, status=302, location="https://www.walmart.com/blocked?x")
    to_slug = raw(_ID_URL, status=301, location="/ip/Midea-AC/212092810")

    assert fetch._blocked(captcha) and fetch._blocked(rejected)
    assert fetch._blocked(to_blocked)
    assert not fetch._blocked(to_slug)
    assert not fetch._blocked(raw(_ID_URL, _PRODUCT))


async def test_a_slug_that_starts_with_blocked_is_not_a_block():
    to_slug = raw(_ID_URL, status=301, location="/ip/blocked-drain-opener/212092810")

    assert not fetch._blocked(to_slug)


async def test_a_transport_error_moves_to_a_fresh_exit(monkeypatch):
    leased: list[str] = []
    real_lease = sessions.lease_exit

    def lease_exit(prefix, country=None):
        exit = real_lease(prefix, country)
        leased.append(exit.sticky)
        return exit

    monkeypatch.setattr(sessions, "lease_exit", lease_exit)
    failures = [http.TransportError("ProxyError", 56, 10.0, "CONNECT refused")]

    def respond(url: str) -> http.RawResponse:
        if failures:
            raise failures.pop()
        return raw(url, _PRODUCT)

    asked = answering(monkeypatch, respond)

    result = await fetch.fetch_page(_ID_URL)

    assert result is not None
    assert len(asked) == 2
    assert len(leased) == 1  # the gateway first, then one sticky exit


async def test_blocks_on_every_exit_give_up_after_four_tries(monkeypatch):
    asked = answering(monkeypatch, lambda url: raw(url, status=403))

    assert await fetch.fetch_page(_ID_URL) is None
    assert len(asked) == 4


async def test_a_slow_try_is_raced_by_a_second_exit(monkeypatch):
    """Past the hedge delay a second exit starts; the first page back wins."""
    calls = 0

    async def slow_then_fast(url: str) -> http.RawResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.sleep(30)  # a stalled proxy tunnel
        return raw(url, _PRODUCT)

    asked = answering(monkeypatch, slow_then_fast)
    started = time.monotonic()

    result = await fetch.fetch_page(_ID_URL, hedge_after_s=0.05)

    assert result is not None and result.status == 200
    assert time.monotonic() - started < 5
    assert len(asked) == 2
    assert sessions.live_sessions() == 0  # the slow try's session was closed


async def test_a_page_never_takes_longer_than_its_budget(monkeypatch):
    async def stalled(url: str) -> http.RawResponse:
        await asyncio.sleep(30)
        return raw(url, _PRODUCT)

    answering(monkeypatch, stalled)
    monkeypatch.setattr(fetch, "_PAGE_BUDGET_S", 0.2)
    started = time.monotonic()

    assert await fetch.fetch_page(_ID_URL, hedge_after_s=0.05) is None
    assert time.monotonic() - started < 5
    assert sessions.live_sessions() == 0


async def test_each_fetch_reports_its_stages(monkeypatch):
    statuses = [403, 200]
    answering(
        monkeypatch,
        lambda url: raw(url, _PRODUCT if statuses[0] == 200 else "", statuses.pop(0)),
    )
    heard: list[str] = []

    async def report(message: str) -> None:
        heard.append(message)

    with fetch.reporting(report):
        await fetch.fetch_page(_ID_URL, stage="product")

    assert heard == [
        "fetching a product page (try 1)",
        "fetching a product page (try 2)",
        "fetched a product page",
    ]
