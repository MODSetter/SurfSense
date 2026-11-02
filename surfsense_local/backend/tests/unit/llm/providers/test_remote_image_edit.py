"""A remote edit model: the picture and the instruction go to `/images/edits`."""

import base64

import httpx
import pytest

from modules.llm.providers.openai_compatible.image_edit import (
    OpenAICompatibleImageEditor,
)
from modules.llm.providers.openai_compatible.image_response import (
    NonRetryableImageError,
)
from modules.llm.providers.protocols import GeneratedImage

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

BASE = GeneratedImage(b"\x89PNG\r\n\x1a\nbase", "image/png")
EDITED = b"\x89PNG\r\n\x1a\nedited"


async def _allow_any(_url: str) -> None:
    return None


def _editor(
    reply: httpx.Response, asked: list[httpx.Request]
) -> OpenAICompatibleImageEditor:
    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        return reply

    return OpenAICompatibleImageEditor(
        "https://example.test/v1/",
        "sk-test",
        allow_url_host=_allow_any,
        transport=httpx.MockTransport(answer),
    )


async def test_it_posts_the_picture_and_the_instruction_as_a_form() -> None:
    """One picture, as OpenAI's edit route takes it."""
    asked: list[httpx.Request] = []
    reply = httpx.Response(
        200, json={"data": [{"b64_json": base64.b64encode(EDITED).decode()}]}
    )

    image = await _editor(reply, asked).edit("gpt-image-1", "make it night", BASE)

    assert image == GeneratedImage(EDITED, "image/png")
    [request] = asked
    assert request.url == "https://example.test/v1/images/edits"
    assert request.headers["authorization"] == "Bearer sk-test"
    form = request.read()
    assert request.headers["content-type"].startswith("multipart/form-data")
    assert b'name="model"\r\n\r\ngpt-image-1' in form
    assert b'name="prompt"\r\n\r\nmake it night' in form
    assert b'name="image"; filename="image.png"' in form
    assert b"Content-Type: image/png" in form
    assert BASE.content in form
    # Only some GPT image models take it, and the rest refuse the request.
    assert b"input_fidelity" not in form


async def test_a_refused_edit_is_not_retried() -> None:
    """A 5xx may follow billed work."""
    asked: list[httpx.Request] = []

    with pytest.raises(NonRetryableImageError, match="500"):
        await _editor(httpx.Response(500, json={}), asked).edit("m", "x", BASE)
    assert len(asked) == 1


async def test_an_answer_with_no_picture_fails_the_edit() -> None:
    """Read as a generation's answer is."""
    with pytest.raises(NonRetryableImageError, match="no data list"):
        await _editor(httpx.Response(200, json={"error": "?"}), []).edit("m", "x", BASE)
