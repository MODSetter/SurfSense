"""Speech recognition models in the one local catalog, offered by audio.cpp,
and `transcription.json`, which Electron starts the second audio.cpp server
from."""

import json
import os
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.integration.llm.installs import install_curated

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

NEMOTRON = "nemotron-3.5-asr-streaming-0.6b"
NEMOTRON_Q8 = "nemotron-3.5-asr-streaming-0.6b-q8_0"
KOKORO_Q8 = "kokoro-82m-q8_0"


def audio_rows(body: dict) -> dict[str, dict]:
    """The rows audio.cpp offered, by id."""
    return {r["id"]: r for r in body["rows"] if r["engine"] == "audiocpp"}


async def install(
    client: AsyncClient, model: str, quantization: str = "Q8_0", **body: object
) -> dict:
    """Install one curated audio.cpp build, its `Q8_0` unless told otherwise."""
    return await install_curated(client, model, quantization, **body)


async def choose(client: AsyncClient, model_type: str, name: str):
    """Fill a slot with an installed audio.cpp build, as Settings' Use does."""
    return await client.put(
        f"/llm/selection/{model_type}",
        json={"provider": "audiocpp", "connection_id": None, "name": name},
    )


def transcription_config(audio_dir: Path) -> dict:
    """The speech server's config as Electron reads it."""
    return json.loads((audio_dir / "transcription.json").read_text())


async def test_a_recogniser_row_says_what_transcribing_takes_and_hears(
    client: AsyncClient, audio_dir
) -> None:
    """The speech recognition section reads these; the server states none."""
    rows = audio_rows((await client.get("/llm/catalog/local")).json())

    nemotron = rows[NEMOTRON]
    assert nemotron["types"] == ["speech_to_text"]
    assert nemotron["selectable_for"] == ["speech_to_text"]
    assert nemotron["runnable"] and nemotron["voicing"] is None
    assert nemotron["lead"] == {"quantization": "Q8_0", "why": "default"}
    transcription = nemotron["transcription"]
    assert transcription["peak_mb"] == 1776
    assert transcription["window_s"] == 28
    assert transcription["detects_language"] is True
    assert len(transcription["languages"]) == 26
    assert transcription["languages"][:3] == ["it", "es", "en"]
    assert rows["kokoro-82m"]["transcription"] is None


async def test_installing_a_recogniser_names_it_in_transcription_json_only(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """Its own server, its own file: the voices' `server.json` never names it,
    so installing it cannot restart a podcast's server."""
    await install(client, NEMOTRON)

    assert (audio_dir / f"{NEMOTRON_Q8}.gguf").exists()
    assert not (audio_dir / "server.json").exists()
    assert transcription_config(audio_dir) == {
        "lazy_load": True,
        "models": [
            {
                "id": NEMOTRON_Q8,
                "family": "nemotron_asr",
                "path": (audio_dir / f"{NEMOTRON_Q8}.gguf").as_posix(),
                "task": "asr",
                "mode": "offline",
                # The multipart routes take no options of their own.
                "default_request_options": {"keep_language_tags": True},
            }
        ],
    }


async def test_a_voice_install_leaves_transcription_json_untouched(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """Electron restarts the speech server whenever the file changes, which
    would cut off a recording or a dictation for nothing."""
    from modules.llm.catalog.local.dependencies import get_local_catalog

    await install(client, NEMOTRON)
    config = audio_dir / "transcription.json"
    os.utime(config, (0, 0))

    await install(client, "kokoro-82m")
    get_local_catalog().audiocpp.on_startup()

    assert config.stat().st_mtime == 0
    voices = json.loads((audio_dir / "server.json").read_text())["models"]
    assert [m["id"] for m in voices] == [KOKORO_Q8]


async def test_deleting_the_last_recogniser_removes_transcription_json(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """The server refuses an empty model list, so the file goes and Electron
    stops the speech server."""
    await install(client, NEMOTRON, select=True)

    reply = await client.delete(f"/llm/models/{NEMOTRON_Q8}")

    assert reply.status_code == 200, reply.text
    assert reply.json()["selection_cleared"] is True
    assert not (audio_dir / f"{NEMOTRON_Q8}.gguf").exists()
    assert not (audio_dir / "transcription.json").exists()
    assert (await client.get("/llm/selection/speech_to_text")).status_code == 404


async def test_a_recogniser_installed_with_select_takes_the_speech_slot(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """The row's own type, not the engine's first: audio.cpp fills two slots."""
    job = await install(client, NEMOTRON, select=True)

    selection = job["event"]["selection"]
    assert (selection["model_type"], selection["provider"], selection["name"]) == (
        "speech_to_text",
        "audiocpp",
        NEMOTRON_Q8,
    )
    assert job["model_types"] == ["speech_to_text"]


async def test_a_voice_installed_with_select_still_takes_the_audio_slot(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """The same rule from the voices' side."""
    job = await install(client, "kitten-tts-mini-0.8", "orig", select=True)

    assert job["event"]["selection"]["model_type"] == "audio_gen"


@pytest.mark.parametrize(
    ("model_type", "name", "status"),
    [
        pytest.param("speech_to_text", NEMOTRON_Q8, 200, id="a recogniser hears"),
        pytest.param("audio_gen", NEMOTRON_Q8, 422, id="a recogniser cannot speak"),
        pytest.param("speech_to_text", KOKORO_Q8, 422, id="a voice cannot hear"),
    ],
)
async def test_each_audio_model_fills_only_its_own_slot(
    client: AsyncClient,
    audio_dir,
    fake_hub,
    model_type: str,
    name: str,
    status: int,
) -> None:
    """A slot must never name a model that cannot do its job."""
    await install(client, NEMOTRON)
    await install(client, "kokoro-82m")

    reply = await choose(client, model_type, name)

    assert reply.status_code == status, reply.text


async def test_a_recogniser_not_installed_cannot_be_chosen(
    client: AsyncClient, audio_dir
) -> None:
    """Electron would start the speech server on nothing."""
    reply = await choose(client, "speech_to_text", NEMOTRON_Q8)

    assert reply.status_code == 422, reply.text


async def test_the_chosen_voice_and_recogniser_each_lead_as_in_use(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """Each section marks its own slot's model."""
    await install(client, NEMOTRON, select=True)
    await install(client, "kokoro-82m", select=True)

    rows = audio_rows((await client.get("/llm/catalog/local")).json())

    for row, slot in ((NEMOTRON, "speech_to_text"), ("kokoro-82m", "audio_gen")):
        assert rows[row]["lead"] == {"quantization": "Q8_0", "why": "in_use"}, row
        (build,) = [b for b in rows[row]["builds"] if b["quantization"] == "Q8_0"]
        assert build["selected_for"] == [slot], row


async def test_deleting_a_recogniser_its_server_holds_open_restarts_that_server(
    client: AsyncClient, audio_dir, fake_hub, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses to delete a file the speech server has open, and its
    config changes no bytes on a retry, so the delete rewrites it anyway: that
    is what restarts the server. The voices' server is left alone."""
    await install(client, NEMOTRON, select=True)
    await install(client, "kokoro-82m")
    weights = audio_dir / f"{NEMOTRON_Q8}.gguf"
    config = audio_dir / "transcription.json"
    voices = audio_dir / "server.json"
    os.utime(config, (0, 0))
    os.utime(voices, (0, 0))
    unlink = Path.unlink

    def held_open(self: Path, missing_ok: bool = False) -> None:
        if self == weights:
            raise PermissionError(32, "The process cannot access the file", str(self))
        unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", held_open)

    reply = await client.delete(f"/llm/models/{NEMOTRON_Q8}")

    assert reply.status_code == 409, reply.text
    assert weights.exists()
    assert config.stat().st_mtime > 0
    assert voices.stat().st_mtime == 0
    assert (await client.get("/llm/selection/speech_to_text")).status_code == 200

    monkeypatch.setattr(Path, "unlink", unlink)
    again = await client.delete(f"/llm/models/{NEMOTRON_Q8}")

    assert again.status_code == 200, again.text
    assert not config.exists()


async def test_a_build_with_no_audio_cpp_offers_no_recogniser(
    client: AsyncClient,
) -> None:
    """No audio folder means Electron staged no audio.cpp for this host."""
    body = (await client.get("/llm/catalog/local")).json()

    assert NEMOTRON not in {r["id"] for r in body["rows"]}
