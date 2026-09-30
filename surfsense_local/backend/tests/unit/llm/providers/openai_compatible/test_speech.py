"""Podcast voices from a server's /audio/speech, against a stub of it."""

import asyncio
import io
import json
import wave

import httpx
import pytest

from modules.llm.providers.openai_compatible.speech import (
    NonRetryableSpeechError,
    RemoteSpeech,
)
from modules.llm.providers.protocols import SpokenTurn

pytestmark = pytest.mark.unit


def wav(frames: int, rate: int = 24000) -> bytes:
    """What a server answers a WAV speech request with: 16-bit mono PCM."""
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * frames)
    return out.getvalue()


class StubServer:
    def __init__(self, fail_on: int | None = None) -> None:
        self.fail_on = fail_on
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if len(self.requests) == self.fail_on:
            return httpx.Response(
                400, json={"error": {"message": "voice 'nobody' is not valid"}}
            )
        return httpx.Response(200, content=wav(1000))

    def bodies(self) -> list[dict]:
        return [json.loads(request.content) for request in self.requests]


def speak(server: StubServer, turns: list[SpokenTurn]):
    """Voice `turns` through the adapter against `server`."""
    speech = RemoteSpeech(
        "tts-1",
        base_url="https://api.example.com/v1",
        api_key="secret",
        transport=httpx.MockTransport(server),
    )
    return asyncio.run(speech.synthesize(turns, "en"))


def test_each_turn_is_one_speech_request_joined_into_one_wav() -> None:
    """WAV is asked for every time, because only WAV joins without an encoder."""
    server = StubServer()

    audio = speak(server, [SpokenTurn("coral", "Hi."), SpokenTurn("onyx", "Hello.")])

    assert [str(r.url) for r in server.requests] == [
        "https://api.example.com/v1/audio/speech"
    ] * 2
    assert server.requests[0].headers["authorization"] == "Bearer secret"
    assert server.bodies() == [
        {"model": "tts-1", "voice": "coral", "input": "Hi.", "response_format": "wav"},
        {
            "model": "tts-1",
            "voice": "onyx",
            "input": "Hello.",
            "response_format": "wav",
        },
    ]
    assert audio.media_type == "audio/wav"
    with wave.open(io.BytesIO(audio.content)) as joined:
        # Two 1000-frame turns and the 0.35 s pause between speakers.
        assert joined.getnframes() == 2000 + 8400


def test_a_refused_turn_names_the_servers_reason_and_is_not_retried() -> None:
    """A retry would draft and bill the episode again, and fail the same way."""
    server = StubServer(fail_on=2)

    with pytest.raises(NonRetryableSpeechError, match="voice 'nobody' is not valid"):
        speak(server, [SpokenTurn("coral", "Hi."), SpokenTurn("onyx", "Hello.")])


def test_voicing_on_a_server_needs_no_memory_here() -> None:
    """Drafting is never refused for memory the server, not this machine, spends."""
    speech = RemoteSpeech("tts-1", base_url="http://tts", api_key=None)

    asyncio.run(speech.check_memory())


def test_a_server_that_answers_in_another_format_says_so() -> None:
    """Only WAV and MP3 join; Ogg back from a server that ignored the format
    is refused rather than stored as an episode nothing can play whole."""

    def ogg(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"OggS\x00\x02fake opus")

    speech = RemoteSpeech(
        "tts-1",
        base_url="http://tts",
        api_key=None,
        transport=httpx.MockTransport(ogg),
    )

    with pytest.raises(NonRetryableSpeechError, match="not as WAV or MP3"):
        asyncio.run(speech.synthesize([SpokenTurn("coral", "Hi.")], "en"))


def test_a_reply_of_several_wavs_back_to_back_joins_as_all_of_them() -> None:
    """Some servers stream a long line as one WAV per sentence in one body."""

    def stacked(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=wav(600) + wav(400))

    speech = RemoteSpeech(
        "tts-1",
        base_url="http://tts",
        api_key=None,
        transport=httpx.MockTransport(stacked),
    )
    audio = asyncio.run(speech.synthesize([SpokenTurn("coral", "Hi.")], "en"))

    with wave.open(io.BytesIO(audio.content)) as joined:
        assert joined.getnframes() == 1000


# MPEG-1 Layer III, 128 kbit/s, 44.1 kHz, no padding: 417 bytes a frame.
FRAME = b"\xff\xfb\x90\x00" + b"\x00" * 413


def mp3(frames: int, *, tag: bool = True, xing: bool = True) -> bytes:
    """An mp3 as a server sends one: an ID3v2 tag, a Xing frame, audio frames."""
    head = b"ID3\x04\x00\x00\x00\x00\x00\x05" + b"x" * 5 if tag else b""
    info = b"\xff\xfb\x90\x00" + b"\x00" * 32 + b"Xing" + b"\x00" * 377 if xing else b""
    return head + info + FRAME * frames


class MpegOnlyServer:
    """OpenRouter's shape: `wav` is refused, `mp3` answered."""

    def __init__(self) -> None:
        self.formats: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        wanted = json.loads(request.content)["response_format"]
        self.formats.append(wanted)
        if wanted != "mp3":
            return httpx.Response(
                400, json={"error": {"message": "response_format must be mp3 or pcm"}}
            )
        return httpx.Response(200, content=mp3(3))


def test_a_server_that_refuses_wav_voices_the_episode_as_one_mp3() -> None:
    """Asked once, then mp3 for every line; each line's own tag and Xing
    frame go, or a player reads the first line's length as the episode's."""
    server = MpegOnlyServer()
    speech = RemoteSpeech(
        "hexgrad/kokoro-82m",
        base_url="http://tts",
        api_key=None,
        transport=httpx.MockTransport(server),
    )

    audio = asyncio.run(
        speech.synthesize(
            [SpokenTurn("af_heart", "Hi."), SpokenTurn("am_adam", "Hello.")], "en"
        )
    )

    assert server.formats == ["wav", "mp3", "mp3"]
    assert audio.media_type == "audio/mpeg"
    assert audio.content == FRAME * 6


def test_a_refusal_wav_did_not_cause_is_not_asked_again_as_mp3() -> None:
    """Only the first line tries mp3; a later refusal is that line's own."""
    server = StubServer(fail_on=2)

    with pytest.raises(NonRetryableSpeechError, match="turn 2 of 2"):
        speak(server, [SpokenTurn("coral", "Hi."), SpokenTurn("onyx", "Hello.")])
    assert [b["response_format"] for b in server.bodies()] == ["wav", "wav"]


def test_a_line_with_no_voice_leaves_the_voice_to_the_server() -> None:
    """Only "Test voice" sends one: the server speaks in its default, if any."""
    server = StubServer()

    speak(server, [SpokenTurn("", "Hi.")])

    assert "voice" not in server.bodies()[0]
