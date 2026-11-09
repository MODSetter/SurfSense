"""Instagram's endpoint login wall: fail at once, remember it, say what still works.

No network. The 401 body is the one web_profile_info gave every anonymous caller
in the 2026-10-13 smoke test.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from proprietary.instagram import fetch, scraper
from proprietary.instagram.fetch import (
    InstagramAccessBlockedError,
    InstagramLoginRequiredError,
    _current_session,
    fetch_html,
    fetch_json,
)

_PROFILE = "api/v1/users/web_profile_info/"
_REQUIRE_LOGIN = json.loads(
    (Path(__file__).parent / "fixtures/web_profile_info_require_login.json").read_text()
)
_USER = {"data": {"user": {"username": "natgeo"}}}


class _Page:
    def __init__(self, status: int, payload: Any = None, *, cookies=None) -> None:
        self.status = status
        self.url = None
        self.cookies = cookies or {}
        self._payload = payload

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload

    @property
    def body(self) -> bytes:
        return json.dumps(self._payload).encode() if self._payload else b"<html>"


class _Exit:
    """One exit: the home page mints csrftoken; endpoints answer ``status``."""

    def __init__(self, status: int, payload: Any = None) -> None:
        self.status = status
        self.payload = payload
        self.warms = 0
        self.gets = 0

    async def get(self, url, headers=None, cookies=None):
        if url.rstrip("/") == "https://www.instagram.com":
            self.warms += 1
            return _Page(200, cookies={"csrftoken": "x", "mid": "y"})
        self.gets += 1
        return _Page(self.status, self.payload)


class _Holder:
    def __init__(self, exits: list[_Exit]) -> None:
        self._exits = exits
        self.session = exits[0]
        self.rotations = 0
        self.warmed = False

    async def rotate(self):
        self.rotations += 1
        self.session = self._exits[min(self.rotations, len(self._exits) - 1)]
        self.warmed = False
        return self.session

    async def pace(self) -> None:
        return None

    async def close(self) -> None:
        return None


async def _on(holder: _Holder, path: str = _PROFILE, username: str = "natgeo"):
    token = _current_session.set(holder)
    try:
        return await fetch_json(path, {"username": username})
    finally:
        _current_session.reset(token)


def _walled_exits() -> list[_Exit]:
    return [_Exit(401, _REQUIRE_LOGIN) for _ in range(fetch._MAX_ROTATIONS + 1)]


async def test_require_login_fails_at_once_without_rotating() -> None:
    holder = _Holder(_walled_exits())

    with pytest.raises(InstagramLoginRequiredError) as raised:
        await _on(holder)

    assert holder.rotations == 0
    assert (holder.session.warms, holder.session.gets) == (1, 1)
    assert "requires a login for api/v1/users/web_profile_info" in str(raised.value)
    assert "asks again after" in str(raised.value)


async def test_while_latched_every_username_fails_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(InstagramLoginRequiredError):
        await _on(_Holder(_walled_exits()))
    later = _Holder([_Exit(200, _USER)])

    async def no_holder() -> Any:
        raise AssertionError("opened a proxy session while latched")

    monkeypatch.setattr(fetch, "open_proxy_holder", no_holder)
    started = time.perf_counter()
    with pytest.raises(InstagramLoginRequiredError, match="seen at"):
        await _on(later, username="nasa")
    with pytest.raises(InstagramLoginRequiredError):
        await fetch_json(_PROFILE, {"username": "cristiano"})  # no bound session

    assert time.perf_counter() - started < 0.5
    assert (later.session.warms, later.session.gets) == (0, 0)


async def test_the_latch_is_per_endpoint_so_post_pages_still_load() -> None:
    with pytest.raises(InstagramLoginRequiredError):
        await _on(_Holder(_walled_exits()))
    post_exit = _Exit(200, None)
    holder = _Holder([post_exit])
    token = _current_session.set(holder)
    try:
        html = await fetch_html("p/C1abc/")
    finally:
        _current_session.reset(token)

    assert html == "<html>"
    assert post_exit.gets == 1


async def test_after_the_latch_the_next_call_asks_again() -> None:
    with pytest.raises(InstagramLoginRequiredError):
        await _on(_Holder(_walled_exits()))
    key = fetch._endpoint(_PROFILE)
    fetch._login_walls[key] = (time.monotonic() - 1, fetch._login_walls[key][1])

    assert await _on(_Holder([_Exit(200, _USER)])) == _USER
    assert fetch._login_walls == {}


async def test_latch_off_still_fails_fast_but_keeps_no_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fetch, "_LOGIN_WALL_LATCH_S", 0.0)
    walled = _Holder(_walled_exits())
    with pytest.raises(InstagramLoginRequiredError):
        await _on(walled)

    assert walled.rotations == 0
    assert await _on(_Holder([_Exit(200, _USER)])) == _USER


@pytest.mark.parametrize(
    "payload",
    [None, {"message": "checkpoint_required", "status": "fail"}],
    ids=["html", "json-without-require-login"],
)
async def test_other_401s_still_rotate_to_a_fresh_exit(payload: Any) -> None:
    holder = _Holder([_Exit(401, payload), _Exit(200, _USER)])

    assert await _on(holder) == _USER
    assert holder.rotations == 1
    assert fetch._login_walls == {}


async def test_endpoint_fetches_make_one_attempt_per_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    class _Session:
        def __init__(self, **kwargs: Any) -> None:
            seen.update(kwargs)

        async def __aenter__(self) -> _Session:
            return self

    monkeypatch.setattr(fetch, "FetcherSession", _Session)
    monkeypatch.setattr(fetch, "get_proxy_url", lambda: "http://p:1")

    await fetch.open_proxy_holder()

    assert (seen["retries"], seen["timeout"]) == (1, (5, fetch._REQUEST_TIMEOUT_S))


async def _walled_job() -> AsyncIterator[dict[str, Any]]:
    raise InstagramLoginRequiredError("Instagram requires a login for x")
    yield {}  # unreachable; makes this an async generator


async def _blocked_job() -> AsyncIterator[dict[str, Any]]:
    raise InstagramAccessBlockedError("Instagram refused p/C1/ on 3 rotated IPs")
    yield {}


async def test_a_fully_refused_run_reports_the_login_wall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The login wall says what still works, so it wins over a bare refusal."""

    class _Nothing:
        async def close(self) -> None:
            return None

    async def holder() -> _Nothing:
        return _Nothing()

    monkeypatch.setattr(scraper, "open_proxy_holder", holder)
    jobs = [_blocked_job(), _walled_job(), _blocked_job()]

    with pytest.raises(InstagramLoginRequiredError):
        async for _ in scraper.fan_out(jobs, concurrency=1):
            pass


async def test_a_walled_post_leaves_its_shortcode_out_of_the_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def holder() -> _Holder:
        return _Holder(_walled_exits())

    monkeypatch.setattr(scraper, "open_proxy_holder", holder)

    async def _post() -> AsyncIterator[dict[str, Any]]:
        yield {"html": await fetch_html("p/Csecret123/")}

    caplog.set_level(logging.DEBUG)
    with pytest.raises(InstagramLoginRequiredError) as refused:
        async for _ in scraper.fan_out([_post()], concurrency=1):
            pass

    # The user still hears which post was walled; the log does not.
    assert "p/Csecret123" in str(refused.value)
    assert "target blocked: InstagramLoginRequiredError" in caplog.text
    assert "Csecret123" not in caplog.text


def test_media_items_carry_every_documented_field() -> None:
    item = scraper._emit(
        {"id": "1", "type": "Image", "ownerId": 123, "caption": "hi"},
        input_url="https://www.instagram.com/p/C1/",
    )

    for field in (
        "isPinned",
        "musicInfo",
        "paidPartnership",
        "isCommentsDisabled",
        "videoPlayCount",
        "dataSource",
    ):
        assert field in item
    assert item["ownerId"] == "123"
    assert item["inputUrl"] == "https://www.instagram.com/p/C1/"
    assert item["scrapedAt"]


def test_profile_items_carry_every_documented_field() -> None:
    from proprietary.instagram.parsers import parse_profile
    from proprietary.instagram.schemas import InstagramProfile

    item = scraper._emit(
        parse_profile({"id": "7", "username": "natgeo"}),
        input_url=None,
        model=InstagramProfile,
    )

    assert item["detailKind"] == "profile"
    assert "statistics" in item
    assert "errorDescription" in item


def test_an_item_that_does_not_fit_the_model_is_kept_as_parsed() -> None:
    item = scraper._emit({"id": "1", "type": "Reel"}, input_url=None)

    assert item["type"] == "Reel"
