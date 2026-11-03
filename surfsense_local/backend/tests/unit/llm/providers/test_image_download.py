"""A picture the connected model returns as a link: downloaded as part of that
connection, its redirects included, and never from anything but HTTP."""

import httpx
import pytest

from modules.llm.providers.openai_compatible.image_response import download_image

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

PNG = b"\x89PNG\r\n\x1a\nimage"


def _server(routes: dict[str, httpx.Response]) -> tuple[httpx.MockTransport, list[str]]:
    asked: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return routes[str(request.url)]

    return httpx.MockTransport(answer), asked


def _moved(location: str) -> httpx.Response:
    return httpx.Response(302, headers={"location": location})


def _image() -> httpx.Response:
    return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})


async def test_a_link_and_its_redirects_are_followed_to_the_picture() -> None:
    """Providers store pictures on other sites, DALL-E's on Azure storage."""
    transport, asked = _server(
        {
            "https://api.example.test/i/1": _moved(
                "https://store.blob.core.windows.net/1.png"
            ),
            "https://store.blob.core.windows.net/1.png": _image(),
        }
    )

    image = await download_image("https://api.example.test/i/1", transport=transport)

    assert image.content == PNG
    assert asked[-1] == "https://store.blob.core.windows.net/1.png"


async def test_a_redirect_off_http_is_refused() -> None:
    """No file or other scheme is read, whatever the server says."""
    transport, _ = _server({"https://cdn.example.test/a": _moved("file:///etc/passwd")})

    with pytest.raises(ValueError, match="HTTP"):
        await download_image("https://cdn.example.test/a", transport=transport)


async def test_more_than_three_redirects_fail_the_download() -> None:
    """So a redirect loop ends."""
    hops = [f"https://cdn.example.test/{n}" for n in range(5)]
    transport, _ = _server(
        {hop: _moved(hops[n + 1]) for n, hop in enumerate(hops[:-1])}
    )

    with pytest.raises(httpx.TooManyRedirects):
        await download_image(hops[0], transport=transport)
