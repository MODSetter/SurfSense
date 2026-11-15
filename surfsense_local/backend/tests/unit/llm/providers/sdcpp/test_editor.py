"""A local edit: sd-server's native job route, with the picture as its reference.

Its OpenAI and A1111 edit routes make the picture the starting noise as well,
which re-draws it rather than following the instruction.
"""

import base64
import io
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from PIL import Image

from modules.llm.providers.openai_compatible.image_response import (
    NonRetryableImageError,
)
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.providers.sdcpp.editor import LocalImageEditor
from shared import cancellation

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

SERVED = "klein-Q4_0.gguf"


def _png(width: int, height: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, "PNG")
    return out.getvalue()


BASE = GeneratedImage(_png(768, 1024), "image/png")
EDITED = _png(768, 1024)


class SdServer:
    """sd-server as the editor meets it: serving klein, and one job polled in turn."""

    def __init__(self, *polls: httpx.Response, submit: httpx.Response | None = None):
        self.polls = list(polls)
        self.submit = submit or httpx.Response(
            202, json={"id": "job_1", "status": "queued"}
        )
        self.posted: list[dict] = []
        self.asked: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.asked.append(f"{request.method} {request.url.path}")
        if request.url.path == "/sdapi/v1/sd-models":
            return httpx.Response(200, json=[{"filename": SERVED}])
        if request.url.path == "/sdcpp/v1/img_gen":
            self.posted.append(json.loads(request.content))
            return self.submit
        if request.url.path == "/sdcpp/v1/jobs/job_1/cancel":
            return httpx.Response(200, json={"status": "cancelled"})
        return self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]


def _job(status: str, **fields: object) -> httpx.Response:
    return httpx.Response(200, json={"id": "job_1", "status": status, **fields})


def _done(image: bytes = EDITED) -> httpx.Response:
    encoded = base64.b64encode(image).decode()
    return _job("completed", result={"images": [{"index": 0, "b64_json": encoded}]})


class Runtime:
    def __init__(self) -> None:
        self.held = False

    @asynccontextmanager
    async def given_up(self) -> AsyncIterator[None]:
        self.held = True
        try:
            yield
        finally:
            self.held = False


def _editor(server: SdServer) -> LocalImageEditor:
    return LocalImageEditor(
        "http://127.0.0.1:1",
        SERVED,
        Runtime().given_up,
        interval=0,
        transport=httpx.MockTransport(server),
    )


async def test_it_sends_the_picture_as_a_reference_at_its_own_size() -> None:
    """The launch's size would crop or stretch a picture of another shape."""
    server = SdServer(_job("queued"), _job("generating"), _done())

    image = await _editor(server).edit("klein", "make it night", (BASE,))

    assert image == GeneratedImage(EDITED, "image/png")
    [body] = server.posted
    assert body == {
        "prompt": "make it night",
        "ref_images": [
            "data:image/png;base64," + base64.b64encode(BASE.content).decode()
        ],
        "width": 768,
        "height": 1024,
        "output_format": "png",
    }
    # Never `init_image`: that re-noises the picture instead of editing it.
    assert "init_image" not in body
    assert server.asked.count("GET /sdcpp/v1/jobs/job_1") == 3


async def test_the_text_runtime_is_given_up_until_the_edit_is_back() -> None:
    """They share one card, as a drawn image does."""
    runtime = Runtime()
    seen: list[bool] = []

    def watch(request: httpx.Request) -> httpx.Response:
        seen.append(runtime.held)
        return server(request)

    server = SdServer(_done())
    edit = LocalImageEditor(
        "http://127.0.0.1:1",
        SERVED,
        runtime.given_up,
        interval=0,
        transport=httpx.MockTransport(watch),
    )

    await edit.edit("klein", "make it night", (BASE,))

    assert seen and all(seen)
    assert runtime.held is False


async def test_a_failed_job_fails_the_edit_with_its_reason() -> None:
    """The server's own message is what the user reads."""
    server = SdServer(
        _job("failed", error={"code": "generation_failed", "message": "out of memory"})
    )

    with pytest.raises(NonRetryableImageError, match="out of memory"):
        await _editor(server).edit("klein", "make it night", (BASE,))


@pytest.mark.parametrize("status", [404, 410])
async def test_a_job_the_server_no_longer_has_fails_the_edit(status: int) -> None:
    """Restarted, or the result expired: polling on would wait forever."""
    server = SdServer(httpx.Response(status, json={"error": "gone"}))

    with pytest.raises(NonRetryableImageError, match=str(status)):
        await _editor(server).edit("klein", "make it night", (BASE,))


async def test_a_full_queue_fails_the_edit() -> None:
    """Not retried: the user asked for one edit, and Retry asks again."""
    server = SdServer(_done(), submit=httpx.Response(429, json={"error": "full"}))

    with pytest.raises(NonRetryableImageError, match="429"):
        await _editor(server).edit("klein", "make it night", (BASE,))


async def test_a_cancel_withdraws_the_queued_job() -> None:
    """A generating job cannot be stopped; Electron stops sd-server for that."""
    server = SdServer(_job("queued"))

    class CancelledError(Exception):
        pass

    def cancelled() -> None:
        raise CancelledError

    with cancellation.watching(cancelled), pytest.raises(CancelledError):
        await _editor(server).edit("klein", "make it night", (BASE,))

    assert server.asked[-1] == "POST /sdcpp/v1/jobs/job_1/cancel"


async def test_withdrawing_a_job_waits_only_briefly() -> None:
    """The text runtime is still held then; a hung server must not hold chat for long."""
    server = SdServer(_job("queued"))
    seen: list[httpx.Request] = []

    def watch(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return server(request)

    class CancelledError(Exception):
        pass

    def cancelled() -> None:
        raise CancelledError

    edit = LocalImageEditor(
        "http://127.0.0.1:1",
        SERVED,
        Runtime().given_up,
        interval=0,
        transport=httpx.MockTransport(watch),
    )
    with cancellation.watching(cancelled), pytest.raises(CancelledError):
        await edit.edit("klein", "make it night", (BASE,))

    withdraw = seen[-1]
    assert withdraw.url.path == "/sdcpp/v1/jobs/job_1/cancel"
    assert withdraw.extensions["timeout"]["read"] <= 2


async def test_every_reference_goes_in_at_the_shape_asked_for() -> None:
    """A comic page keeps its characters from page one, drawn portrait at about
    the reference's pixel count, each side a multiple of 64."""
    server = SdServer(_done())
    page_one = GeneratedImage(_png(1024, 1024), "image/png")

    await _editor(server).edit("klein", "page two", (page_one, BASE), shape="portrait")

    [body] = server.posted
    assert body["ref_images"] == [
        "data:image/png;base64," + base64.b64encode(page_one.content).decode(),
        "data:image/png;base64," + base64.b64encode(BASE.content).decode(),
    ]
    assert (body["width"], body["height"]) == (832, 1280)
