"""A remote edit model: the picture and the instruction go to `/images/edits`."""

import base64
import json

import httpx
import pytest

from modules.llm.providers.openai_compatible.image_edit import (
    OpenAICompatibleImageEditor,
    _refused,
    _routes,
)
from modules.llm.providers.openai_compatible.image_response import (
    NonRetryableImageError,
)
from modules.llm.providers.protocols import GeneratedImage

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

BASE = GeneratedImage(b"\x89PNG\r\n\x1a\nbase", "image/png")
EDITED = b"\x89PNG\r\n\x1a\nedited"


def _editor(
    reply: httpx.Response, asked: list[httpx.Request]
) -> OpenAICompatibleImageEditor:
    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        return reply

    return OpenAICompatibleImageEditor(
        "https://example.test/v1/",
        "sk-test",
        transport=httpx.MockTransport(answer),
    )


async def test_it_posts_the_picture_and_the_instruction_as_a_form() -> None:
    """One picture, as OpenAI's edit route takes it."""
    asked: list[httpx.Request] = []
    reply = httpx.Response(
        200, json={"data": [{"b64_json": base64.b64encode(EDITED).decode()}]}
    )

    image = await _editor(reply, asked).edit("gpt-image-1", "make it night", (BASE,))

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
    # The picture itself, not a link to fetch from wherever the provider put it.
    assert b'name="response_format"\r\n\r\nb64_json' in form


async def test_a_refused_edit_is_not_retried() -> None:
    """A 5xx may follow billed work."""
    asked: list[httpx.Request] = []

    with pytest.raises(NonRetryableImageError, match="500"):
        await _editor(httpx.Response(500, json={}), asked).edit("m", "x", (BASE,))
    assert len(asked) == 1


async def test_an_answer_with_no_picture_fails_the_edit() -> None:
    """Read as a generation's answer is."""
    with pytest.raises(NonRetryableImageError, match="no data list"):
        await _editor(httpx.Response(200, json={"error": "?"}), []).edit(
            "m", "x", (BASE,)
        )


async def test_a_model_that_refuses_the_setting_is_asked_again_without_it() -> None:
    """GPT image models answer with the picture and refuse the setting; a 400
    comes before any work, so asking again bills nothing twice."""
    _refused.clear()
    asked: list[bytes] = []
    done = httpx.Response(
        200, json={"data": [{"b64_json": base64.b64encode(EDITED).decode()}]}
    )

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(request.read())
        refused = b"response_format" in asked[-1]
        return httpx.Response(400, json={}) if refused else done

    editor = OpenAICompatibleImageEditor(
        "https://example.test/v1", transport=httpx.MockTransport(answer)
    )
    image = await editor.edit("gpt-image-1", "make it night", (BASE,))

    assert image.content == EDITED
    assert [b"response_format" in form for form in asked] == [True, False]


PAGE_ONE = GeneratedImage(b"\x89PNG\r\n\x1a\npage-one", "image/png")
DONE = {"data": [{"b64_json": base64.b64encode(EDITED).decode()}]}


async def test_several_pictures_go_as_one_part_each() -> None:
    """A comic page keeps its characters from the pages before it."""
    asked: list[httpx.Request] = []
    editor = _editor(httpx.Response(200, json=DONE), asked)

    await editor.edit("gpt-image-1", "page two", (PAGE_ONE, BASE))

    form = asked[0].read()
    assert form.count(b'name="image[]"') == 2
    assert form.index(PAGE_ONE.content) < form.index(BASE.content)


async def test_a_shape_is_asked_for_as_a_size() -> None:
    """As OpenAI's edit route takes it."""
    asked: list[httpx.Request] = []
    editor = _editor(httpx.Response(200, json=DONE), asked)

    await editor.edit("gpt-image-1", "page two", (PAGE_ONE,), shape="portrait")

    assert b'name="size"\r\n\r\n1024x1536' in asked[0].read()


async def test_a_server_with_no_edit_route_is_sent_references_instead() -> None:
    """OpenRouter answers 404 on /images/edits, before any work, and takes the
    pictures as input_references on /images; the route is kept per server."""
    _routes.clear()
    asked: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        if request.url.path.endswith("/images/edits"):
            return httpx.Response(404, json={})
        return httpx.Response(200, json=DONE)

    editor = OpenAICompatibleImageEditor(
        "https://gateway.test/v1", "sk-test", transport=httpx.MockTransport(answer)
    )
    image = await editor.edit(
        "openai/gpt-image-2.6", "page two", (PAGE_ONE,), shape="portrait"
    )
    await editor.edit("openai/gpt-image-2.6", "page three", (PAGE_ONE,))

    assert image.content == EDITED
    assert [r.url.path for r in asked] == [
        "/v1/images/edits",
        "/v1/images",
        "/v1/images",
    ]
    sent = json.loads(asked[1].read())
    assert sent["model"] == "openai/gpt-image-2.6"
    assert sent["prompt"] == "page two"
    assert sent["aspect_ratio"] == "2:3"
    assert sent["input_references"] == [
        {
            "type": "image_url",
            "image_url": {
                "url": "data:image/png;base64,"
                + base64.b64encode(PAGE_ONE.content).decode()
            },
        }
    ]
    assert "aspect_ratio" not in json.loads(asked[2].read())


async def test_a_server_error_on_the_edit_route_is_not_tried_elsewhere() -> None:
    """A 5xx may follow billed work: no second route, no second picture."""
    _routes.clear()
    asked: list[httpx.Request] = []

    with pytest.raises(NonRetryableImageError, match="502"):
        await _editor(httpx.Response(502, json={}), asked).edit("m", "x", (BASE,))
    assert len(asked) == 1


class _CutOff(httpx.AsyncByteStream):
    """A body the server stops sending partway, as OpenRouter did after a 404."""

    async def __aiter__(self):
        yield b'{"error": {"message": "Not Fou'
        raise httpx.RemoteProtocolError(
            "peer closed connection without sending complete message body "
            "(incomplete chunked read)"
        )


async def test_a_missing_edit_route_cut_off_mid_reply_still_sends_references() -> None:
    """Its 404 says there is no such route before any work; the body adds nothing,
    so a server that hangs up while sending it is no reason to fail the page."""
    _routes.clear()
    asked: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        if request.url.path.endswith("/images/edits"):
            return httpx.Response(404, stream=_CutOff())
        return httpx.Response(200, json=DONE)

    editor = OpenAICompatibleImageEditor(
        "https://cutoff.test/v1", "sk-test", transport=httpx.MockTransport(answer)
    )
    image = await editor.edit("google/gemini-2.5-flash-image", "page two", (PAGE_ONE,))

    assert image.content == EDITED
    assert [r.url.path for r in asked] == ["/v1/images/edits", "/v1/images"]


async def test_a_picture_cut_off_mid_reply_still_fails() -> None:
    """A success must arrive whole: half a picture is no picture."""
    _routes.clear()
    asked: list[httpx.Request] = []

    with pytest.raises(NonRetryableImageError, match="incomplete chunked read"):
        await _editor(httpx.Response(200, stream=_CutOff()), asked).edit(
            "m", "x", (BASE,)
        )
    assert len(asked) == 1
