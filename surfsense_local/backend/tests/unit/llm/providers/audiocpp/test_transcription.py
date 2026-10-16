"""Speech written down by the transcription server, against a stub of it."""

import io
import json
import wave

import httpx
import pytest

from modules.llm.activity import ModelBusyError, model_activity, model_key
from modules.llm.providers.audiocpp.transcription import AudioCppTranscriber
from modules.llm.providers.protocols import TranscriptionUnavailableError

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

MODEL = "nemotron-3.5-asr-streaming-0.6b-q8_0"
KEY = model_key("audiocpp", MODEL)


def wav(seconds: float) -> bytes:
    """A silent clip of `seconds` at the recogniser's rate."""
    out = io.BytesIO()
    with wave.open(out, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(16000)
        clip.writeframes(b"\0\0" * int(16000 * seconds))
    return out.getvalue()


def listing(loaded: bool, model: str = MODEL) -> dict:
    """How the server lists its models: one entry per config entry."""
    return {
        "object": "list",
        "data": [{"id": model, "task": "asr", "mode": "offline", "loaded": loaded}],
    }


def failure(status: int, message: str) -> httpx.Response:
    """How audio.cpp's server answers a request it failed."""
    return httpx.Response(
        status, json={"error": {"message": message, "type": "server_error"}}
    )


def client(handler, **kwargs) -> AudioCppTranscriber:
    """The app's client over a stub of the server."""
    return AudioCppTranscriber(
        "http://transcription", transport=httpx.MockTransport(handler), **kwargs
    )


def form(request: httpx.Request) -> dict[str, str]:
    """The multipart fields a request carried, a file by its file name."""
    boundary = request.headers["content-type"].split("boundary=")[1].encode()
    fields = {}
    for part in request.content.split(b"--" + boundary)[1:-1]:
        head, _, body = part.partition(b"\r\n\r\n")
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        if b"filename=" in head:
            filename = head.split(b'filename="')[1].split(b'"')[0].decode()
            fields[name] = f"file:{filename}"
        else:
            fields[name] = body.removesuffix(b"\r\n").decode()
    return fields


async def test_a_clip_is_sent_as_a_wav_file_with_the_model_and_its_locale() -> None:
    """From memory, as multipart to the details route."""
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"text": "Hola. <es-ES>", "language": "es-ES"})

    text = await client(answer).transcribe(MODEL, wav(1.0), "es-ES")

    assert text == "Hola. <es-ES>"
    (request,) = seen
    assert request.url.path == "/v1/audio/transcriptions/details"
    # The server refuses any file name ending in something other than .wav.
    assert form(request) == {
        "file": "file:audio.wav",
        "model": MODEL,
        "language": "es-ES",
    }


async def test_with_no_locale_the_model_detects_it() -> None:
    """Auto sends no language at all."""
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"text": ""})

    await client(answer).transcribe(MODEL, wav(0.5), None)

    assert "language" not in form(seen[0])


@pytest.mark.parametrize(
    ("seconds", "deadline"),
    [
        pytest.param(4.0, 120, id="two minutes at least"),
        pytest.param(28.0, 560, id="twenty times a long window"),
    ],
)
async def test_the_deadline_grows_with_the_audio(seconds: float, deadline: int) -> None:
    """A hung server fails one window, not the job."""
    timeouts: list[dict] = []

    def answer(request: httpx.Request) -> httpx.Response:
        timeouts.append(request.extensions["timeout"])
        return httpx.Response(200, json={"text": ""})

    await client(answer).transcribe(MODEL, wav(seconds), None)

    assert timeouts[0]["read"] == deadline


@pytest.mark.parametrize(
    "first",
    [
        pytest.param(httpx.ConnectError("refused"), id="a refused connection"),
        pytest.param(failure(503, "server_busy"), id="a 503"),
    ],
)
async def test_a_server_restarting_is_asked_once_more(first) -> None:
    """As during a restart after a crash or a new config."""
    replies = [first, httpx.Response(200, json={"text": "again"})]

    def answer(request: httpx.Request) -> httpx.Response:
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    transcriber = client(answer, retry_after=0)

    assert await transcriber.transcribe(MODEL, wav(1.0), None) == "again"


async def test_a_second_failure_says_the_server_is_unavailable() -> None:
    """One retry only: the caller decides what comes next."""

    def answer(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(TranscriptionUnavailableError):
        await client(answer, retry_after=0).transcribe(MODEL, wav(1.0), None)


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param(httpx.ReadTimeout("hung"), id="past its deadline"),
        pytest.param(httpx.Response(200, text="<html>"), id="an unreadable reply"),
    ],
)
async def test_a_hung_or_garbled_server_is_unavailable_not_asked_again(reply) -> None:
    """A hung server fails one window, not the job: the route answers 503
    rather than an error the worker cannot read."""
    asked: list[int] = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(1)
        if isinstance(reply, Exception):
            raise reply
        return reply

    with pytest.raises(TranscriptionUnavailableError):
        await client(answer, retry_after=0).transcribe(MODEL, wav(1.0), None)
    assert len(asked) == 1


async def test_a_failure_the_server_explains_is_not_asked_again() -> None:
    """Its own words are kept for the reason."""
    asked: list[int] = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(1)
        return failure(500, "unknown model id: nemotron")

    with pytest.raises(TranscriptionUnavailableError, match="unknown model id"):
        await client(answer, retry_after=0).transcribe(MODEL, wav(1.0), None)
    assert len(asked) == 1


async def test_the_model_is_in_use_while_the_request_runs() -> None:
    """So a delete in the middle is refused rather than pulling the file."""
    refused: list[bool] = []

    async def answer(request: httpx.Request) -> httpx.Response:
        try:
            async with model_activity.deleting(KEY):
                refused.append(False)
        except ModelBusyError:
            refused.append(True)
        return httpx.Response(200, json={"text": ""})

    await client(answer).transcribe(MODEL, wav(1.0), None)

    assert refused == [True]
    async with model_activity.deleting(KEY):
        pass  # free again once the request ends


async def test_a_model_being_deleted_is_not_sent_a_request() -> None:
    """The delete has the model; nothing loads it again."""
    asked: list[int] = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(1)
        return httpx.Response(200, json={"text": ""})

    async with model_activity.deleting(KEY):
        with pytest.raises(ModelBusyError):
            await client(answer).transcribe(MODEL, wav(1.0), None)
    assert asked == []


@pytest.mark.parametrize("loaded", [True, False])
async def test_the_server_says_whether_the_model_is_loaded(loaded: bool) -> None:
    """Admission skips its memory check for a loaded model."""

    def answer(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json=listing(loaded))

    assert await client(answer).is_loaded(MODEL) is loaded


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param(httpx.ConnectError("refused"), id="no server"),
        pytest.param(
            httpx.Response(200, json=listing(True, "other")), id="not its model"
        ),
    ],
)
async def test_a_server_not_serving_the_model_is_unavailable(reply) -> None:
    """As in the seconds after a new model's config, before the restart."""

    def answer(request: httpx.Request) -> httpx.Response:
        if isinstance(reply, Exception):
            raise reply
        return reply

    with pytest.raises(TranscriptionUnavailableError):
        await client(answer).is_loaded(MODEL)


async def test_unloading_names_the_model() -> None:
    """By id, never every model."""
    seen: list[tuple[str, dict]] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"unloaded": [MODEL], "not_found": []})

    await client(answer).unload(MODEL)

    assert seen == [("/v1/tasks/unload_models", {"model_ids": [MODEL]})]


async def test_an_unload_that_fails_is_left_to_the_idle_timer() -> None:
    """Five idle minutes unload it anyway."""

    def answer(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    await client(answer).unload(MODEL)
