"""Speech recognition behind the API: dictation's routes for the composer and
the windows route for the ingest worker, against a stand-in of the
transcription server."""

import asyncio
import io
import threading
import time
import wave
from collections.abc import Iterator

import httpx
import numpy as np
import pytest
import uvicorn
from httpx import AsyncClient

from api.main import create_app
from shared.db import create_session_factory
from tests.integration.llm.installs import install_curated
from tests.integration.llm.transcription_stand_in import MODEL, TranscriptionServer

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

NEMOTRON = "nemotron-3.5-asr-streaming-0.6b"
CANARY = "canary-180m-flash"
CANARY_MODEL = "canary-180m-flash-q8_0"
NEEDED = 1776 * 2**20 + 2**30


def wav(seconds: float, *, rate: int = 16000, loud: bool = True) -> bytes:
    """A clip as the composer sends one; loud enough to pass for a voice when
    no detector is staged, silent otherwise."""
    samples = np.zeros(int(seconds * rate), dtype="<i2")
    if loud:
        samples[::2] = 3000
    out = io.BytesIO()
    with wave.open(out, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(rate)
        clip.writeframes(samples.tobytes())
    return out.getvalue()


def detail(reply) -> dict:
    """The refusal's body, as the screen reads it."""
    return reply.json()["detail"]


@pytest.fixture
async def speech_model(client: AsyncClient, audio_dir, fake_hub) -> str:
    """Nemotron downloaded and chosen, as Settings leaves it."""
    await install_curated(client, NEMOTRON, "Q8_0", select=True)
    return MODEL


@pytest.fixture
def plenty_of_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """A computer with room for the speech model."""
    monkeypatch.setattr(
        "modules.llm.hardware.system_memory.available_bytes", lambda: 16 * 2**30
    )


@pytest.fixture
def short_of_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """A computer 1.8 GB short of free memory."""
    monkeypatch.setattr(
        "modules.llm.hardware.system_memory.available_bytes", lambda: 1_800_000_000
    )


@pytest.fixture
def quick_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """The windows route's 30 s wait and 5 s memory poll, cut for the test."""
    monkeypatch.setattr("modules.llm.transcription.internal_router.WAIT_SECONDS", 0.3)
    monkeypatch.setattr(
        "modules.llm.transcription.internal_router.MEMORY_POLL_SECONDS", 0.05
    )


async def open_dictation(client: AsyncClient) -> str:
    """Press the mic: a new dictation's id."""
    opened = await client.post("/llm/transcription/dictations")
    assert opened.status_code == 201, opened.text
    return opened.json()["id"]


async def phrase(client: AsyncClient, dictation: str, clip: bytes):
    """Send one phrase of a dictation, as the composer does."""
    return await client.post(
        f"/llm/transcription/dictations/{dictation}/phrases",
        files={"audio": ("phrase.wav", clip, "audio/wav")},
    )


async def window(client: AsyncClient, clip: bytes, **form: str):
    """Send one window of a recording, as the ingest worker does."""
    return await client.post(
        "/internal/transcription/windows",
        files={"audio": ("window.wav", clip, "audio/wav")},
        data=form,
    )


# Status


async def test_with_no_speech_model_status_says_to_choose_one(
    client: AsyncClient, audio_dir
) -> None:
    """The mic and a waiting recording open the set-up popover."""
    reply = await client.get("/llm/transcription/status")

    assert reply.status_code == 200, reply.text
    assert reply.json() == {
        "ready": False,
        "reason": "needs_speech_model",
        "model": None,
        "language_intent": "auto",
        "languages": [],
    }


async def test_with_no_server_running_status_says_it_is_unavailable(
    client: AsyncClient, speech_model: str
) -> None:
    """As in the seconds after a model is chosen, before Electron starts it."""
    body = (await client.get("/llm/transcription/status")).json()

    assert (body["ready"], body["reason"], body["model"]) == (
        False,
        "transcription_unavailable",
        MODEL,
    )


async def test_a_chosen_model_on_a_running_server_is_ready(
    client: AsyncClient, speech_model: str, transcription_server: TranscriptionServer
) -> None:
    """With the language the user set and the ones the model lists."""
    await client.put("/llm/selection/speech_to_text/language", json={"language": "ja"})

    body = (await client.get("/llm/transcription/status")).json()

    assert (body["ready"], body["reason"], body["model"]) == (True, None, MODEL)
    assert body["language_intent"] == "ja"
    assert len(body["languages"]) == 26


# Opening a dictation


async def test_dictation_needs_a_speech_model(
    client: AsyncClient, audio_dir, transcription_server: TranscriptionServer
) -> None:
    """The mic opens the set-up popover instead."""
    reply = await client.post("/llm/transcription/dictations")

    assert reply.status_code == 409, reply.text
    assert detail(reply)["code"] == "needs_speech_model"


async def test_dictation_needs_the_server(
    client: AsyncClient, speech_model: str
) -> None:
    """No server answers, so dictation cannot start."""
    reply = await client.post("/llm/transcription/dictations")

    assert reply.status_code == 503, reply.text
    assert detail(reply)["code"] == "transcription_unavailable"


async def test_dictation_short_of_memory_is_refused_before_anyone_speaks(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    short_of_memory,
) -> None:
    """Both sizes, so the screen says it in the user's language."""
    reply = await client.post("/llm/transcription/dictations")

    assert reply.status_code == 409, reply.text
    assert detail(reply) == {
        "code": "transcription_needs_memory",
        "needed_bytes": NEEDED,
        "available_bytes": 1_800_000_000,
        "message": "Transcribing needs about 2.9 GB free; this computer has 1.8 GB.",
    }
    assert transcription_server.requests == []


async def test_a_loaded_model_needs_no_memory_check_or_warming(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    short_of_memory,
) -> None:
    """The operating system's figure already leaves a loaded model out."""
    transcription_server.loaded = True

    reply = await client.post("/llm/transcription/dictations")

    assert reply.status_code == 201, reply.text
    assert reply.json()["warm"] == "loaded"
    await asyncio.sleep(0.1)
    assert transcription_server.requests == []


async def test_opening_warms_the_model_with_half_a_second_of_silence(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    plenty_of_memory,
) -> None:
    """So it loads while the speaker starts talking."""
    reply = await client.post("/llm/transcription/dictations")

    assert reply.status_code == 201, reply.text
    assert reply.json()["warm"] == "loading"
    for _ in range(100):
        if transcription_server.loaded:
            break
        await asyncio.sleep(0.02)
    assert transcription_server.requests == [{"model": MODEL, "seconds": 0.5}]


# Phrases


async def test_a_phrase_comes_back_without_its_tags_in_the_language_heard(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
) -> None:
    """The last locale tag names the language; none is left in the text."""
    transcription_server.loaded = True
    transcription_server.text = "Hola a todos. <es-ES>"
    dictation = await open_dictation(client)

    reply = await phrase(client, dictation, wav(2.0))

    assert reply.status_code == 200, reply.text
    assert reply.json() == {
        "text": "Hola a todos.",
        "language": "es",
        "no_speech": False,
    }
    # Auto: no language named, so the model detects it.
    assert transcription_server.requests == [{"model": MODEL, "seconds": 2.0}]


async def test_a_language_the_user_set_reaches_the_model_as_its_locale(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
) -> None:
    """Nemotron takes ja-JP, not ja."""
    transcription_server.loaded = True
    transcription_server.text = "こんにちは"
    await client.put("/llm/selection/speech_to_text/language", json={"language": "ja"})
    dictation = await open_dictation(client)

    reply = await phrase(client, dictation, wav(1.0))

    assert reply.json() == {"text": "こんにちは", "language": "ja", "no_speech": False}
    assert transcription_server.requests[0]["language"] == "ja-JP"


async def test_a_model_that_cannot_detect_is_always_told_the_language(
    client: AsyncClient,
    audio_dir,
    fake_hub,
    transcription_server: TranscriptionServer,
) -> None:
    """Canary told nothing translates German speech into English."""
    await install_curated(client, CANARY, "Q8_0", select=True)
    transcription_server.models = [CANARY_MODEL]
    transcription_server.loaded = True
    transcription_server.text = "The report is due."
    dictation = await open_dictation(client)

    reply = await phrase(client, dictation, wav(1.0))

    assert reply.json() == {
        "text": "The report is due.",
        "language": "en",
        "no_speech": False,
    }
    assert transcription_server.requests[0]["language"] == "en"


async def test_a_quiet_phrase_never_reaches_the_model(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    real_silero_vad,
) -> None:
    """A cough, a keystroke or a pause: Silero hears under 250 ms of speech."""
    transcription_server.loaded = True
    dictation = await open_dictation(client)

    reply = await phrase(client, dictation, wav(2.0, loud=False))

    assert reply.json() == {"text": "", "language": None, "no_speech": True}
    assert transcription_server.requests == []


@pytest.mark.parametrize(
    "clip",
    [
        pytest.param(b"RIFF....not audio", id="not a WAV"),
        pytest.param(wav(1.0, rate=48000), id="the device's rate"),
        pytest.param(wav(31.0), id="over 30 s"),
    ],
)
async def test_a_phrase_the_model_cannot_read_is_refused(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    clip: bytes,
) -> None:
    """Checked before anything reaches the server."""
    transcription_server.loaded = True
    dictation = await open_dictation(client)

    reply = await phrase(client, dictation, clip)

    assert reply.status_code == 422, reply.text
    assert detail(reply)["code"] == "unfit_audio"
    assert transcription_server.requests == []


async def test_a_phrase_for_a_dictation_the_api_does_not_know_has_ended(
    client: AsyncClient, speech_model: str, transcription_server: TranscriptionServer
) -> None:
    """As after an API restart: the composer stops and keeps its text."""
    reply = await phrase(client, "gone", wav(1.0))

    assert reply.status_code == 404, reply.text
    assert detail(reply)["code"] == "dictation_ended"


async def test_a_server_restarting_mid_phrase_is_asked_once_more(
    client: AsyncClient, speech_model: str, transcription_server: TranscriptionServer
) -> None:
    """A 503 while the server restarts costs one retry, not the phrase."""
    transcription_server.loaded = True
    transcription_server.text = "Still here."
    dictation = await open_dictation(client)
    transcription_server.failures = [503]

    reply = await phrase(client, dictation, wav(1.0))

    assert reply.json()["text"] == "Still here."


async def test_a_server_that_keeps_failing_is_unavailable(
    client: AsyncClient, speech_model: str, transcription_server: TranscriptionServer
) -> None:
    """The composer offers Retry from the audio it kept."""
    transcription_server.loaded = True
    dictation = await open_dictation(client)
    transcription_server.failures = [503, 503]

    reply = await phrase(client, dictation, wav(1.0))

    assert reply.status_code == 503, reply.text
    assert detail(reply)["code"] == "transcription_unavailable"


async def test_a_phrase_after_the_model_is_deleted_ends_the_dictation(
    client: AsyncClient, speech_model: str, transcription_server: TranscriptionServer
) -> None:
    """The speech model was removed, so no later phrase can land."""
    transcription_server.loaded = True
    dictation = await open_dictation(client)
    await client.delete(f"/llm/models/{MODEL}")

    reply = await phrase(client, dictation, wav(1.0))
    kept = await client.post(f"/llm/transcription/dictations/{dictation}/keepalive")

    assert reply.status_code == 409, reply.text
    assert detail(reply)["code"] == "needs_speech_model"
    assert kept.status_code == 404


async def test_keepalives_hold_a_dictation_until_it_is_closed(
    client: AsyncClient, speech_model: str, transcription_server: TranscriptionServer
) -> None:
    """Closing after the last phrase lets recordings go on."""
    transcription_server.loaded = True
    dictation = await open_dictation(client)

    kept = await client.post(f"/llm/transcription/dictations/{dictation}/keepalive")
    closed = await client.delete(f"/llm/transcription/dictations/{dictation}")
    after = await client.post(f"/llm/transcription/dictations/{dictation}/keepalive")

    assert (kept.status_code, closed.status_code, after.status_code) == (204, 204, 404)


async def test_opening_a_second_dictation_ends_the_first(
    client: AsyncClient, speech_model: str, transcription_server: TranscriptionServer
) -> None:
    """One dictation at a time holds the server."""
    transcription_server.loaded = True
    first = await open_dictation(client)
    await open_dictation(client)

    reply = await phrase(client, first, wav(1.0))

    assert detail(reply)["code"] == "dictation_ended"


# A recording's windows


async def test_a_window_comes_back_with_its_language_and_the_model(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    plenty_of_memory,
) -> None:
    """The model id lets a job resume only windows the same model wrote."""
    transcription_server.text = "Bom dia a todos. <pt-PT>"

    reply = await window(client, wav(28.0))

    assert reply.status_code == 200, reply.text
    assert reply.json() == {
        "text": "Bom dia a todos.",
        "language": "pt",
        "model_id": MODEL,
    }
    assert transcription_server.unloaded == []


async def test_a_window_needs_a_speech_model(
    client: AsyncClient, audio_dir, transcription_server: TranscriptionServer
) -> None:
    """The recording then waits for one to be chosen."""
    reply = await window(client, wav(1.0))

    assert reply.status_code == 409, reply.text
    assert detail(reply)["code"] == "needs_speech_model"


async def test_no_window_is_sent_while_someone_dictates(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    quick_windows,
) -> None:
    """The speaker's phrases never queue behind a recording."""
    transcription_server.loaded = True
    await open_dictation(client)

    reply = await window(client, wav(1.0))

    assert reply.status_code == 503, reply.text
    assert (detail(reply)["code"], detail(reply)["reason"]) == ("waiting", "dictation")
    assert transcription_server.requests == []


async def test_windows_go_again_once_the_dictation_is_closed(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    quick_windows,
) -> None:
    """Closing the dictation frees the server at once."""
    transcription_server.loaded = True
    dictation = await open_dictation(client)
    await client.delete(f"/llm/transcription/dictations/{dictation}")

    reply = await window(client, wav(1.0))

    assert reply.status_code == 200, reply.text


async def test_a_window_waits_for_memory_then_says_so_with_both_sizes(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    short_of_memory,
    quick_windows,
) -> None:
    """The job counts these waits toward its 10 minutes."""
    reply = await window(client, wav(1.0))

    assert reply.status_code == 503, reply.text
    assert detail(reply) == {
        "code": "waiting",
        "reason": "memory",
        "needed_bytes": NEEDED,
        "available_bytes": 1_800_000_000,
        "message": "Transcribing needs about 2.9 GB free; this computer has 1.8 GB.",
    }
    assert transcription_server.requests == []


async def test_the_last_window_gives_the_model_back(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    plenty_of_memory,
) -> None:
    """As a podcast does when it ends: no other recording is waiting."""
    reply = await window(client, wav(1.0), last="true")

    assert reply.status_code == 200, reply.text
    assert transcription_server.unloaded == [MODEL]


async def test_the_last_window_keeps_the_model_for_a_dictation_opened_meanwhile(
    client: AsyncClient,
    speech_model: str,
    transcription_server: TranscriptionServer,
    plenty_of_memory,
) -> None:
    """The speaker's first phrase would only load it again."""
    transcription_server.release = threading.Event()
    sent = asyncio.create_task(window(client, wav(1.0), last="true"))
    await asyncio.to_thread(transcription_server.running.wait, 5)
    await open_dictation(client)
    transcription_server.release.set()

    reply = await sent

    assert reply.status_code == 200, reply.text
    assert transcription_server.unloaded == []


# A podcast or an image holding the text runtime


@pytest.fixture
def live(engine) -> Iterator[str]:
    """The app on a real port, so a held stream can be read as it arrives."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=0, lifespan="off", log_level="warning"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
    server.should_exit = True
    thread.join(timeout=5)


async def test_a_hold_lets_the_window_finish_unloads_the_model_and_keeps_dictation(
    speech_model: str,
    transcription_server: TranscriptionServer,
    llamacpp_server: str,
    live: str,
    plenty_of_memory,
    quick_windows,
) -> None:
    """While a podcast voices: no recording's window starts, the one in flight
    finishes first, the speech model gives its memory back, and the speaker
    can still dictate."""
    transcription_server.release = threading.Event()
    async with httpx.AsyncClient(base_url=live, timeout=10) as api:
        in_flight = asyncio.create_task(window(api, wav(1.0)))
        await asyncio.to_thread(transcription_server.running.wait, 5)
        yielded = asyncio.Event()

        async def hold() -> None:
            async with api.stream("POST", "/internal/models/text/yield") as held:
                async for line in held.aiter_lines():
                    if '"yielded"' in line:
                        yielded.set()

        holding = asyncio.create_task(hold())
        await asyncio.sleep(0.2)
        granted_mid_window = yielded.is_set()
        transcription_server.release.set()
        finished = await in_flight
        await asyncio.wait_for(yielded.wait(), 5)
        unloaded = list(transcription_server.unloaded)

        held_back = await window(api, wav(1.0))
        dictation = await open_dictation(api)
        spoken = await phrase(api, dictation, wav(1.0))
        await api.delete(f"/llm/transcription/dictations/{dictation}")

        holding.cancel()
        await asyncio.gather(holding, return_exceptions=True)
        await asyncio.sleep(0.2)
        after = await window(api, wav(1.0))

    assert not granted_mid_window
    assert finished.status_code == 200, finished.text
    assert unloaded == [MODEL]
    assert (held_back.status_code, detail(held_back)["reason"]) == (503, "hold")
    assert spoken.status_code == 200, spoken.text
    assert after.status_code == 200, after.text
