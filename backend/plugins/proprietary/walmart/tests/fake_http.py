"""Walmart faked at the shared transport's seam, `scraping.http.request`.

The plugin's holders, leases, hedging and block tests all run for real; only the
request itself is answered here, with no network.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

import pytest

from proprietary.scraping import http

_TIMINGS = http.Timings(
    new_conn=True,
    connect_ms=0.0,
    tls_ms=0.0,
    ttfb_ms=0.0,
    total_ms=0.0,
    bytes_wire=0,
)

Answer = http.RawResponse | Awaitable[http.RawResponse]


def raw(
    url: str,
    body: str = "",
    status: int = 200,
    *,
    location: str | None = None,
) -> http.RawResponse:
    """A response as the transport returns one."""
    headers = {"content-type": "text/html; charset=utf-8"}
    if location is not None:
        headers["location"] = location
    return http.RawResponse(
        status=status,
        url=url,
        headers=headers,
        cookies={},
        body=body.encode("utf-8"),
        history=(),
        timings=_TIMINGS,
    )


def answering(
    monkeypatch: pytest.MonkeyPatch, respond: Callable[[str], Answer]
) -> list[str]:
    """Answer every request with `respond(url)`; keeps each URL asked for, in order.

    `respond` may return a coroutine, to keep a request in flight.
    """
    asked: list[str] = []

    async def request(
        method: str,
        url: str,
        *,
        is_blocked: Callable[[http.RawResponse], bool] | None = None,
        **_: Any,
    ) -> http.RawResponse:
        asked.append(url)
        answer = respond(url)
        response = answer if isinstance(answer, http.RawResponse) else await answer
        if (is_blocked or http.default_blocked)(response):
            response = replace(response, blocked=True)
        return response

    monkeypatch.setattr(http, "request", request)
    return asked
