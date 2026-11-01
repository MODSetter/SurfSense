"""An image endpoint that answers with a URL: every host the download reaches,
redirects included, passes the egress check before it is asked."""

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


class Egress:
    """The caller's egress decision: allows the hosts given, refuses the rest."""

    def __init__(self, *allowed: str) -> None:
        self.allowed = allowed
        self.checked: list[str] = []

    async def __call__(self, url: str) -> None:
        self.checked.append(url)
        if httpx.URL(url).host not in self.allowed:
            raise PermissionError(f"{httpx.URL(url).host} is off")


async def test_a_redirect_to_an_allowed_host_is_checked_then_followed() -> None:
    """A CDN the user allowed serves the picture the endpoint pointed at."""
    transport, asked = _server(
        {
            "https://api.example.test/i/1": _moved("https://cdn.example.test/1.png"),
            "https://cdn.example.test/1.png": _image(),
        }
    )
    egress = Egress("api.example.test", "cdn.example.test")

    image = await download_image(
        "https://api.example.test/i/1", egress, transport=transport
    )

    assert image.content == PNG
    assert egress.checked == ["https://cdn.example.test/1.png"]
    assert asked == ["https://api.example.test/i/1", "https://cdn.example.test/1.png"]


async def test_a_redirect_to_a_host_egress_refuses_is_never_asked() -> None:
    """Following it unchecked would send the request where the user said no."""
    transport, asked = _server(
        {"https://api.example.test/i/1": _moved("https://tracker.example.test/x")}
    )

    with pytest.raises(PermissionError, match=r"tracker\.example\.test"):
        await download_image(
            "https://api.example.test/i/1",
            Egress("api.example.test"),
            transport=transport,
        )
    assert asked == ["https://api.example.test/i/1"]


async def test_a_relative_redirect_stays_on_the_host_it_came_from() -> None:
    """Resolved against the URL that answered, and checked as any hop is."""
    transport, asked = _server(
        {
            "https://cdn.example.test/a": _moved("/b.png"),
            "https://cdn.example.test/b.png": _image(),
        }
    )

    image = await download_image(
        "https://cdn.example.test/a", Egress("cdn.example.test"), transport=transport
    )

    assert image.content == PNG
    assert asked[-1] == "https://cdn.example.test/b.png"


async def test_a_redirect_off_http_is_refused() -> None:
    """No file or other scheme is read, whatever the server says."""
    transport, _ = _server({"https://cdn.example.test/a": _moved("file:///etc/passwd")})

    with pytest.raises(ValueError, match="HTTP"):
        await download_image(
            "https://cdn.example.test/a",
            Egress("cdn.example.test"),
            transport=transport,
        )


async def test_more_than_three_redirects_fail_the_download() -> None:
    """As many as httpx was allowed before, so a loop ends."""
    hops = [f"https://cdn.example.test/{n}" for n in range(5)]
    transport, _ = _server(
        {hop: _moved(hops[n + 1]) for n, hop in enumerate(hops[:-1])}
    )

    egress = Egress("cdn.example.test")

    with pytest.raises(ValueError, match="redirect"):
        await download_image(hops[0], egress, transport=transport)
    # The fourth redirect's host is never checked: it would be recorded for nothing.
    assert egress.checked == hops[1:4]
