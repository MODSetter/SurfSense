"""Podcast voices from audio.cpp's server, against a stub of it."""

import asyncio
import io
import json
import wave

import httpx
import pytest

from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.providers.audiocpp.speech import (
    AudioCppSpeech,
    NotEnoughMemoryError,
    VoicedModel,
)
from modules.llm.providers.protocols import SpokenTurn

pytestmark = pytest.mark.unit

MODELS = {m.id: m for m in load_local_manifest().models}


def voiced(model_id: str, installed_as: str) -> VoicedModel:
    """A curated model as the resolver hands it over: its server id and entry."""
    audio = MODELS[model_id].audio
    assert audio is not None
    return VoicedModel(installed_as, audio)


def test_the_voices_are_the_chosen_models_roster() -> None:
    """A Supertonic voice speaks every language the model does; a Kokoro voice
    speaks its own."""
    kokoro = AudioCppSpeech(voiced("kokoro-82m", "kokoro-82m-q8_0"), base_url="")
    supertonic = AudioCppSpeech(voiced("supertonic-3", "supertonic-3-f16"), base_url="")

    heart = next(v for v in kokoro.voices() if v.id == "af_heart")
    assert (heart.label, heart.languages) == ("Heart", ("en-US",))
    m1 = next(v for v in supertonic.voices() if v.id == "M1")
    assert len(m1.languages) == 31 and "fr" in m1.languages


def wav(frames: int, rate: int = 24000) -> bytes:
    """What the server answers a speech request with: 16-bit mono PCM."""
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * frames)
    return out.getvalue()


class StubServer:
    """audio.cpp's routes as the adapter calls them, recording each request."""

    def __init__(self, frames: int = 1000, fail_on: int | None = None) -> None:
        self.frames = frames
        self.fail_on = fail_on
        self.requests: list[tuple[str, dict]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        self.requests.append((request.url.path, body))
        if request.url.path == "/v1/audio/speech":
            if len(self.speech()) == self.fail_on:
                return httpx.Response(500, json={"error": "voicing failed"})
            return httpx.Response(200, content=wav(self.frames))
        return httpx.Response(200, json={"unloaded": []})

    def speech(self) -> list[dict]:
        return [body for path, body in self.requests if path == "/v1/audio/speech"]


PLENTY = 64 * 2**30


def speak(model: VoicedModel, server: StubServer, turns, language="en-US", free=PLENTY):
    """Voice `turns` through the adapter against `server`, with `free` bytes."""
    speech = AudioCppSpeech(
        model,
        base_url="http://audio",
        transport=httpx.MockTransport(server),
        available=lambda: free,
    )
    return asyncio.run(speech.synthesize(turns, language))


def test_each_turn_is_one_request_and_the_turns_join_with_a_pause() -> None:
    """0.35 s between speakers, as the podcast has always had, at the model's rate."""
    server = StubServer(frames=1000)
    turns = [SpokenTurn("am_adam", "Welcome back."), SpokenTurn("af_heart", "Thanks.")]

    audio = speak(voiced("kokoro-82m", "kokoro-82m-q8_0"), server, turns)

    assert audio.media_type == "audio/wav"
    assert [(b["model"], b["voice"], b["input"]) for b in server.speech()] == [
        ("kokoro-82m-q8_0", "am_adam", "Welcome back."),
        ("kokoro-82m-q8_0", "af_heart", "Thanks."),
    ]
    with wave.open(io.BytesIO(audio.content)) as joined:
        assert joined.getframerate() == 24000
        # Two turns of 1,000 frames around 8,400 frames of silence.
        assert joined.getnframes() == 10_400


def test_the_language_is_sent_only_where_the_voice_speaks_several() -> None:
    """Supertonic reads it from the request; a Kokoro voice's name already
    fixes it, and Kokoro's codes differ from the manifest's."""
    supertonic, kokoro = StubServer(), StubServer()

    speak(
        voiced("supertonic-3", "supertonic-3-f16"),
        supertonic,
        [SpokenTurn("F1", "Bonjour.")],
        language="fr",
    )
    speak(
        voiced("kokoro-82m", "kokoro-82m-q8_0"),
        kokoro,
        [SpokenTurn("ff_siwis", "Bonjour.")],
        language="fr",
    )

    assert supertonic.speech()[0]["language"] == "fr"
    assert "language" not in kokoro.speech()[0]


@pytest.mark.parametrize("fail_on", [None, 2], ids=["voiced", "a turn failed"])
def test_the_model_is_unloaded_when_voicing_ends(fail_on: int | None) -> None:
    """The memory is known free to give back then, whatever the timer says; the
    chat model drafts the next job's text in it."""
    server = StubServer(fail_on=fail_on)
    turns = [SpokenTurn("am_adam", "One."), SpokenTurn("af_heart", "Two.")]

    if fail_on is None:
        speak(voiced("kokoro-82m", "kokoro-82m-q8_0"), server, turns)
    else:
        with pytest.raises(httpx.HTTPStatusError):
            speak(voiced("kokoro-82m", "kokoro-82m-q8_0"), server, turns)

    assert server.requests[-1][0] == "/v1/tasks/unload_all_models"


def test_voicing_refuses_before_loading_when_memory_is_short() -> None:
    """The server's own guard counts the 190 MB file, not the 1.4 GB Kokoro
    takes while voicing, so the app checks the measured peak plus 1 GiB."""
    server = StubServer()

    with pytest.raises(NotEnoughMemoryError) as refused:
        speak(
            voiced("kokoro-82m", "kokoro-82m-q8_0"),
            server,
            [SpokenTurn("af_heart", "Hello.")],
            free=2**30,
        )

    assert str(refused.value) == (
        "Voicing needs about 2.6 GB free; this computer has 1.1 GB."
    )
    assert server.speech() == []
