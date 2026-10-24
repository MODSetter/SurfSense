"""Amazon faked at the plugin's network seam, the shared ``http.request``."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

import pytest

from proprietary.amazon import fetch
from proprietary.scraping.http import RawResponse, Timings

_TIMINGS = Timings(
    new_conn=True,
    connect_ms=0.0,
    tls_ms=0.0,
    ttfb_ms=0.0,
    total_ms=0.0,
    bytes_wire=0,
)


def raw(
    url: str,
    html: str = "",
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> RawResponse:
    return RawResponse(
        status=status,
        url=url,
        headers=headers or {},
        cookies=cookies or {},
        body=html.encode(),
        history=(),
        timings=_TIMINGS,
    )


Answer = Callable[[str, dict[str, Any]], Awaitable[RawResponse]]


def answering(monkeypatch: pytest.MonkeyPatch, answer: Answer) -> list[dict[str, Any]]:
    """Route every Amazon request to ``answer(url, kwargs)``; returns what was sent."""
    sent: list[dict[str, Any]] = []

    async def request(method: str, url: str, **kwargs: Any) -> RawResponse:
        sent.append({"method": method, "url": url, **kwargs})
        response = await answer(url, kwargs)
        blocked = (kwargs.get("is_blocked") or (lambda _r: False))(response)
        return replace(response, blocked=blocked)

    monkeypatch.setattr(fetch.http, "request", request)
    monkeypatch.setattr(fetch, "get_geo_proxy_url", lambda country=None: None)
    return sent
