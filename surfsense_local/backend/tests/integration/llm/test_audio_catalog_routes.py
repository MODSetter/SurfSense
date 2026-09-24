"""Audio models in the one local catalog, offered by audio.cpp, and the
`server.json` Electron starts audio.cpp's server from."""

import json

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

AUDIO_IDS = {"kokoro-82m", "supertonic-3", "kitten-tts-mini-0.8"}


def audio_rows(body: dict) -> dict[str, dict]:
    """The rows audio.cpp offered, by id."""
    return {r["id"]: r for r in body["rows"] if r["engine"] == "audiocpp"}


async def test_audio_models_are_rows_with_no_fit_claim(
    client: AsyncClient, audio_dir
) -> None:
    """Runnable, downloadable, and silent about this machine."""
    body = (await client.get("/llm/catalog/local")).json()

    rows = audio_rows(body)
    assert set(rows) == AUDIO_IDS
    kokoro = rows["kokoro-82m"]
    assert kokoro["types"] == ["audio_gen"]
    assert kokoro["runnable"] and not kokoro["recommended"]
    assert kokoro["lead"] == {"quantization": "Q8_0", "why": "default"}
    assert all(b["fit"] is None and b["can_install"] for b in kokoro["builds"])


async def test_a_build_with_no_audio_cpp_offers_no_audio_rows(
    client: AsyncClient,
) -> None:
    """No audio folder means Electron staged no audio.cpp for this host."""
    body = (await client.get("/llm/catalog/local")).json()

    assert not audio_rows(body)


async def install(client: AsyncClient, model: str, quantization: str) -> list[dict]:
    """Install one curated audio build through the one install stream."""
    body = (await client.get("/llm/catalog/local")).json()
    (build,) = [
        b
        for b in audio_rows(body)[model]["builds"]
        if b["quantization"] == quantization
    ]
    reply = await client.post(
        "/llm/install", json={"catalog_id": build["catalog_id"], "select": False}
    )
    return [json.loads(line) for line in reply.text.splitlines()]


async def test_an_audio_build_installs_into_its_folder_and_names_itself_in_the_config(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """Electron starts audio.cpp's server from `server.json` and restarts it
    when the file changes, so the install is what makes the model reachable."""
    events = await install(client, "kokoro-82m", "Q8_0")

    assert events[-1]["type"] == "complete", events[-1]
    assert (audio_dir / "kokoro-82m-q8_0.gguf").exists()
    config = json.loads((audio_dir / "server.json").read_text())
    assert config == {
        "lazy_load": True,
        "models": [
            {
                "id": "kokoro-82m-q8_0",
                "family": "kokoro_tts",
                "path": (audio_dir / "kokoro-82m-q8_0.gguf").as_posix(),
                "task": "tts",
                "mode": "offline",
            }
        ],
    }


async def test_deleting_audio_models_rewrites_the_config_and_the_last_removes_it(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """The server refuses an empty model list, so with nothing left installed
    the file goes and Electron stops the server."""
    await install(client, "kokoro-82m", "Q8_0")
    await install(client, "kitten-tts-mini-0.8", "orig")

    reply = await client.delete("/llm/models/kokoro-82m-q8_0")

    assert reply.status_code == 200, reply.text
    assert not (audio_dir / "kokoro-82m-q8_0.gguf").exists()
    config = json.loads((audio_dir / "server.json").read_text())
    assert [m["id"] for m in config["models"]] == ["kitten-tts-mini-0.8-orig"]

    reply = await client.delete("/llm/models/kitten-tts-mini-0.8-orig")

    assert reply.status_code == 200, reply.text
    assert not (audio_dir / "server.json").exists()
