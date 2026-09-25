"""A Studio job waits for sd-server to serve its model: Electron starts it on
its next poll after the job needs it, a few seconds later."""

import httpx
import pytest

from modules.llm.providers.protocols import GeneratedImage
from modules.llm.providers.sdcpp.generator import LocalImageGenerator
from modules.llm.providers.sdcpp.serving import (
    ImageServerNotReadyError,
    wait_until_serving,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def server(*answers: object) -> tuple[httpx.MockTransport, list[str]]:
    """Answer each poll in turn, the last one repeated; None refuses the
    connection, as a port nothing listens on does."""
    asked: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.path)
        answer = answers[min(len(asked), len(answers)) - 1]
        if answer is None:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json=[{"filename": answer}])

    return httpx.MockTransport(reply), asked


async def test_it_waits_until_sd_server_serves_this_model() -> None:
    """Not up yet, then still on the model the last job used, then this one."""
    transport, asked = server(None, "sd15.gguf", "klein-Q4_0.gguf")

    await wait_until_serving(
        "http://127.0.0.1:1", "klein-Q4_0.gguf", interval=0, transport=transport
    )

    assert asked == ["/sdapi/v1/sd-models"] * 3


async def test_a_server_that_never_comes_up_fails_the_job_with_a_reason() -> None:
    """Waiting forever would hold one of Studio's four threads."""
    transport, _ = server(None)

    with pytest.raises(ImageServerNotReadyError, match="did not start"):
        await wait_until_serving(
            "http://127.0.0.1:1", "klein-Q4_0.gguf", timeout=0, transport=transport
        )


async def test_the_local_image_generator_posts_only_once_its_model_is_served() -> None:
    """Posting before then would find nothing listening, or the wrong model."""
    transport, asked = server(None, "klein-Q4_0.gguf")
    posted: list[str] = []

    class Inner:
        async def generate(self, model: str, prompt: str) -> GeneratedImage:
            posted.append(prompt)
            return GeneratedImage(b"png", "image/png")

    generator = LocalImageGenerator(
        Inner(),
        "http://127.0.0.1:1",
        "klein-Q4_0.gguf",
        interval=0,
        transport=transport,
    )

    image = await generator.generate("klein-Q4_0", "a lighthouse")

    assert len(asked) == 2 and posted == ["a lighthouse"]
    assert image.content == b"png"
