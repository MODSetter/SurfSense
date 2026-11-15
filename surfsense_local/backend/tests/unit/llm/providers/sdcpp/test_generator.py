"""A local drawing: today's route as it was, and the native job route when a
shape is asked, since only that one takes a width and height per request."""

import httpx
import pytest

from modules.llm.providers.protocols import GeneratedImage
from modules.llm.providers.sdcpp.generator import LocalImageGenerator
from tests.unit.llm.providers.sdcpp.test_editor import (
    EDITED,
    SERVED,
    Runtime,
    SdServer,
    _done,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class Inner:
    """Today's client, reaching sd-server's OpenAI route."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    async def generate(self, model: str, prompt: str) -> GeneratedImage:
        self.asked.append(prompt)
        return GeneratedImage(b"square", "image/png")


def _generator(server: SdServer, inner: Inner) -> LocalImageGenerator:
    return LocalImageGenerator(
        inner,
        "http://127.0.0.1:1",
        SERVED,
        Runtime().given_up,
        pixels=1024 * 1024,
        interval=0,
        transport=httpx.MockTransport(server),
    )


async def test_a_drawing_with_no_shape_keeps_its_route() -> None:
    """Nothing changes for a picture that asks for no shape."""
    server, inner = SdServer(_done()), Inner()

    image = await _generator(server, inner).generate("klein", "a lighthouse")

    assert image.content == b"square"
    assert inner.asked == ["a lighthouse"]
    assert server.posted == []


async def test_a_shape_is_drawn_through_the_native_route_at_its_size() -> None:
    """At the launch's pixel count, in the shape's proportions."""
    server, inner = SdServer(_done()), Inner()

    image = await _generator(server, inner).generate(
        "klein", "a comic page", shape="portrait"
    )

    assert image == GeneratedImage(EDITED, "image/png")
    assert inner.asked == []
    [body] = server.posted
    assert body == {
        "prompt": "a comic page",
        "width": 832,
        "height": 1280,
        "output_format": "png",
    }
