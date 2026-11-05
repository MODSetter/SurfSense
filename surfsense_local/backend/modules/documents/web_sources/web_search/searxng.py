"""One page of a SearXNG server's results, from its JSON API.

The server must serve JSON (`search.formats` lists `json` in its settings.yml);
a stock install answers 403 until it does.
"""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

# A server waits on its engines for a few seconds; past this it is not answering.
TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# SearXNG's bot detection turns away a request with no Accept-Language, and one
# whose User-Agent names an HTTP library. `*` asks for no language in particular.
_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "*",
    "User-Agent": "SurfSense",
}


class SearchUnreachableError(Exception):
    """The server did not answer."""


class SearchFailedError(Exception):
    """The server answered, but with no search: refused, broken, or every engine failed."""


@dataclass(frozen=True)
class Found:
    url: str
    title: str | None
    description: str | None


async def searxng_page(server: str, query: str, page: int) -> list[Found]:
    """`page` counts from 0; SearXNG's own count starts at 1."""
    # httpx decodes an IDNA host in each request's URL; urlsplit would not.
    server_url = httpx.URL(server)
    host = server_url.host
    secure = server_url.scheme == "https"

    async def same_host(request: httpx.Request) -> None:
        # A redirect stays on the server the user was asked about, never leaving https.
        if request.url.host != host or (secure and request.url.scheme != "https"):
            raise SearchFailedError(
                f"redirected to {request.url.scheme}://{request.url.host}"
            )

    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            headers=_HEADERS,
            follow_redirects=True,
            event_hooks={"request": [same_host]},
        ) as client:
            response = await client.get(
                f"{server}/search",
                params={
                    "q": query,
                    "format": "json",
                    "pageno": page + 1,
                    "categories": "general",
                },
            )
    except httpx.HTTPError as error:
        raise SearchUnreachableError(str(error)) from error
    if response.status_code != 200:
        raise SearchFailedError(f"HTTP {response.status_code}")
    try:
        answer = response.json()
    except ValueError as error:
        raise SearchFailedError("not JSON") from error
    # SearXNG's answer always lists its results, even none: anything else is no search.
    results = answer.get("results") if isinstance(answer, dict) else None
    if not isinstance(results, list):
        raise SearchFailedError("no results list")
    found = _found(results)
    if not found and answer.get("unresponsive_engines"):
        raise SearchFailedError(f"no engine answered: {answer['unresponsive_engines']}")
    return found


def _found(results: list[Any]) -> list[Found]:
    """Web links only, each once, in the server's order."""
    found: list[Found] = []
    seen: set[str] = set()
    for result in results:
        url = result.get("url") if isinstance(result, dict) else None
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        if url in seen or not _names_a_host(url):
            continue
        seen.add(url)
        found.append(
            Found(url, _text(result.get("title")), _text(result.get("content")))
        )
    return found


def _names_a_host(url: str) -> bool:
    """A row is built from the link's parts: one urlsplit refuses fails the search."""
    try:
        return bool(urlsplit(url).hostname)
    except ValueError:
        return False


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return " ".join(value.split()) or None
