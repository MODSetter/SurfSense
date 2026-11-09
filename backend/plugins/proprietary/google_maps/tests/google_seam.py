"""Points the plugin's requests at a fake Google, at the shared transport's seam.

Every request the plugin sends, on a job's kept session or on a fresh exit, goes
through ``proprietary.scraping.http.request``; the fake answers it with what a
test's ``get(url, **kw)`` returns, a page as text, so no test touches the network.
"""

from dataclasses import dataclass, field, replace
from typing import Any

import pytest

from proprietary.google_maps import fetch
from proprietary.scraping import http

_TIMINGS = http.Timings(True, 0.0, 0.0, 0.0, 0.0, 0)


@dataclass
class Page:
    """What Google answers one GET with."""

    html_content: str
    status: int = 200
    cookies: dict[str, str] = field(default_factory=dict)
    url: str | None = None  # where a redirect ended, when it did


def answer_with(monkeypatch: pytest.MonkeyPatch, get: Any) -> None:
    """Send every request to ``get(url, cookies=, session=, timeout=)``."""

    async def request(
        method: str,
        url: str,
        *,
        plugin: str,
        stage: str,
        proxy: str | None,
        session: Any = None,
        cookies: dict[str, str] | None = None,
        timeout: tuple[float, float] = http.DEFAULT_TIMEOUT,  # noqa: ASYNC109
        is_blocked: Any = None,
        **_: Any,
    ) -> http.RawResponse:
        page = await get(url, cookies=cookies or {}, session=session, timeout=timeout)
        response = http.RawResponse(
            status=page.status,
            url=page.url or url,
            headers={},
            cookies=page.cookies,
            body=page.html_content.encode(),
            history=(),
            timings=_TIMINGS,
        )
        if (is_blocked or http.default_blocked)(response):
            response = replace(response, blocked=True)
        return response

    monkeypatch.setattr(http, "request", request)
    # A browser render would mean a refusal still reaches for Chromium.
    monkeypatch.setattr(fetch, "StealthyFetcher", None)
