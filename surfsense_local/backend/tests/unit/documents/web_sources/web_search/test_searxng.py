"""Where a search may go, redirects included.

httpx's own transport answers here, so a test can name any host.
"""

from collections.abc import Callable

import httpx
import pytest

from modules.documents.web_sources.web_search import searxng
from modules.documents.web_sources.web_search.searxng import (
    Found,
    SearchFailedError,
    searxng_page,
)

pytestmark = pytest.mark.unit

RESULTS = {"results": [{"url": "https://tides.example/explained", "title": "Tides"}]}


def answered_by(
    monkeypatch: pytest.MonkeyPatch,
    answer: Callable[[httpx.Request], httpx.Response],
) -> list[str]:
    """The addresses the search asked, in order."""
    asked: list[str] = []
    real_client = httpx.AsyncClient

    def handle(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return answer(request)

    def client(**kwargs: object) -> httpx.AsyncClient:
        return real_client(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(searxng.httpx, "AsyncClient", client)
    return asked


async def test_a_redirect_from_https_to_http_is_not_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On the same host too: the query would go on in plain text."""

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.scheme == "https":
            location = str(request.url.copy_with(scheme="http"))
            return httpx.Response(302, headers={"location": location})
        return httpx.Response(200, json=RESULTS)

    asked = answered_by(monkeypatch, answer)

    with pytest.raises(SearchFailedError):
        await searxng_page("https://search.firm.example", "tides", 0)

    assert [url.split("?")[0] for url in asked] == [
        "https://search.firm.example/search"
    ]


async def test_a_server_named_in_punycode_is_searched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its first request is on the server's own host, however its name is written."""
    asked = answered_by(monkeypatch, lambda _: httpx.Response(200, json=RESULTS))

    found = await searxng_page("https://xn--bcher-kva.example", "tides", 0)

    assert found == [Found("https://tides.example/explained", "Tides", None)]
    assert len(asked) == 1
