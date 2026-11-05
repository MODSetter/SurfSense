"""Voicing against a stub of ElevenLabs, its refusals as the live API sends them."""

import asyncio
import io
import json
import wave

import httpx
import pytest

from modules.llm.providers.elevenlabs import speech as speech_module
from modules.llm.providers.elevenlabs.speech import ElevenLabsSpeech
from modules.llm.providers.openai_compatible.speech import NonRetryableSpeechError
from modules.llm.providers.protocols import SpokenTurn

pytestmark = pytest.mark.unit


def wav(frames: int = 1000, rate: int = 24000) -> bytes:
    """What `output_format=wav_24000` answers with: 16-bit mono."""
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * frames)
    return out.getvalue()


def refused(status: int, code: str, message: str) -> httpx.Response:
    """A refusal in the shape ElevenLabs sends."""
    return httpx.Response(
        status, json={"detail": {"status": code, "code": code, "message": message}}
    )


def speak(handler, turns: list[SpokenTurn], language: str = ""):
    """Voice `turns` against `handler` and return the audio."""
    client = ElevenLabsSpeech(
        "eleven_v4",
        base_url="https://api.elevenlabs.io",
        api_key="secret",
        transport=httpx.MockTransport(handler),
    )
    return asyncio.run(client.synthesize(turns, language))


def test_each_line_is_one_request_in_its_voice_joined_with_a_pause() -> None:
    """The key goes as xi-api-key, the voice in the path, and only WAV takes a pause."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=wav())

    audio = speak(handler, [SpokenTurn("sarah", "Hi."), SpokenTurn("george", "Yo.")])

    assert [r.url.path for r in seen] == [
        "/v1/text-to-speech/sarah",
        "/v1/text-to-speech/george",
    ]
    assert seen[0].url.params["output_format"] == "wav_24000"
    assert seen[0].headers["xi-api-key"] == "secret"
    assert "authorization" not in seen[0].headers
    assert json.loads(seen[0].content) == {"text": "Hi.", "model_id": "eleven_v4"}
    assert audio.media_type == "audio/wav"
    with wave.open(io.BytesIO(audio.content)) as joined:
        # Two 1000-frame lines and the 0.35 s pause between speakers.
        assert joined.getnframes() == 2000 + 8400


def test_a_language_goes_with_the_line_since_a_wrong_one_fails_otherwise_silently() -> (
    None
):
    """German on an English-only model answers 200 unless the code is sent."""
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=wav())

    speak(handler, [SpokenTurn("sarah", "Hallo.")], "de")

    assert seen[0]["language_code"] == "de"


def test_a_blank_line_is_not_sent() -> None:
    """ElevenLabs answers one with 200 and a third of a second of silence."""
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content)["text"])
        return httpx.Response(200, content=wav())

    speak(handler, [SpokenTurn("sarah", "Hi."), SpokenTurn("george", "   ")])

    assert sent == ["Hi."]


def test_no_voice_is_refused_before_anything_is_sent() -> None:
    """The voice is in the path, and ElevenLabs has no default to fall back on."""
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, content=wav())

    with pytest.raises(NonRetryableSpeechError, match="voice"):
        speak(handler, [SpokenTurn("", "Hi.")])
    assert sent == []


def test_a_voice_id_cannot_change_the_address() -> None:
    """A typed id reaches the path, so it is quoted."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.raw_path.decode())
        return httpx.Response(200, content=wav())

    speak(handler, [SpokenTurn("a/../b?c", "Hi.")])

    assert seen[0].startswith("/v1/text-to-speech/a%2F..%2Fb%3Fc")


def test_a_concurrency_refusal_waits_and_asks_again(monkeypatch) -> None:
    """Refused at once and not billed, and Studio runs four jobs at a time."""
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(speech_module.asyncio, "sleep", sleep)
    answers = [
        refused(429, "concurrent_limit_exceeded", "Too many concurrent requests."),
        httpx.Response(200, content=wav()),
    ]

    audio = speak(lambda request: answers.pop(0), [SpokenTurn("sarah", "Hi.")])

    assert slept == [1]
    assert audio.media_type == "audio/wav"


def test_a_limit_that_never_clears_ends_with_its_words(monkeypatch) -> None:
    """One first try and four waits, then the episode ends and says why."""

    async def sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(speech_module.asyncio, "sleep", sleep)
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return refused(429, "x", "Too many concurrent requests.")

    with pytest.raises(NonRetryableSpeechError, match="Too many concurrent"):
        speak(handler, [SpokenTurn("sarah", "Hi.")])
    assert len(calls) == 5


@pytest.mark.parametrize(
    ("status", "body", "words"),
    [
        (
            402,
            {"detail": {"status": "payment_required", "message": "Free users cannot"}},
            "Free users cannot",
        ),
        # A bad model's body has neither `type` nor `code`.
        (
            400,
            {"detail": {"status": "model_not_found", "message": "No such model"}},
            "No such model",
        ),
        # FastAPI's own shapes, from a wrong address and a validation error.
        (404, {"detail": "Not Found"}, "Not Found"),
        (
            422,
            {"detail": [{"loc": ["body"], "msg": "Field required"}]},
            "Field required",
        ),
    ],
)
def test_every_shape_of_refusal_shows_its_words_and_is_not_retried(
    status: int, body: dict, words: str
) -> None:
    """A repeat would fail the same way."""
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status, json=body)

    with pytest.raises(NonRetryableSpeechError, match=words):
        speak(handler, [SpokenTurn("sarah", "Hi.")])
    assert len(calls) == 1


def test_a_server_failure_is_not_retried() -> None:
    """Audio may already have been generated, and so billed."""
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500, text="oops")

    with pytest.raises(NonRetryableSpeechError, match="HTTP 500"):
        speak(handler, [SpokenTurn("sarah", "Hi.")])
    assert len(calls) == 1


def test_a_failure_in_an_episode_names_the_line_and_a_trial_does_not() -> None:
    """ "Line 1 of 1" means nothing when one line is being tried."""

    def handler(request: httpx.Request) -> httpx.Response:
        return refused(404, "voice_not_found", "No such voice.")

    with pytest.raises(NonRetryableSpeechError) as one:
        speak(handler, [SpokenTurn("sarah", "Hi.")])
    assert str(one.value) == "No such voice."

    with pytest.raises(NonRetryableSpeechError, match="line 1 of 2: No such voice"):
        speak(handler, [SpokenTurn("sarah", "Hi."), SpokenTurn("george", "Yo.")])


def test_an_unreachable_server_is_not_retried() -> None:
    """The request may have reached it, and may be billed."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(NonRetryableSpeechError, match="down"):
        speak(handler, [SpokenTurn("sarah", "Hi.")])


def test_voicing_needs_no_memory_here() -> None:
    """Drafting is never refused for memory ElevenLabs spends."""
    client = ElevenLabsSpeech("m", base_url="http://x", api_key="k")

    asyncio.run(client.check_memory())
